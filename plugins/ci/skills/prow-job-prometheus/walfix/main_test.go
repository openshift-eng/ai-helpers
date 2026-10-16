package main

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func writeWAL(t *testing.T, dir string, recs []record) {
	t.Helper()
	writeSegment(t, filepath.Join(dir, "00000000"), recs)
}

func writeSegment(t *testing.T, path string, recs []record) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	w, err := newWriter(path)
	if err != nil {
		t.Fatal(err)
	}
	for _, r := range recs {
		if err := w.log(r); err != nil {
			t.Fatal(err)
		}
	}
	if err := w.close(); err != nil {
		t.Fatal(err)
	}
}

func readAll(t *testing.T, dir string) ([]record, stats) {
	t.Helper()
	var got []record
	st, err := repair(dir, t.TempDir(), nil)
	if err != nil {
		t.Fatal(err)
	}
	// Read the input directly so the test checks what readSegment recovers.
	var st2 stats
	b, err := os.ReadFile(filepath.Join(dir, "00000000"))
	if err != nil {
		t.Fatal(err)
	}
	if err := readSegment(b, &st2, func(r record) error { got = append(got, r); return nil }); err != nil {
		t.Fatal(err)
	}
	if st != st2 {
		t.Fatalf("repair stats %+v differ from readSegment stats %+v", st, st2)
	}
	return got, st
}

func TestRoundTrip(t *testing.T) {
	dir := t.TempDir()
	recs := []record{
		{data: []byte("small")},
		{flags: 1 << 3, data: bytes.Repeat([]byte("x"), 3*pageSize)}, // spans pages, keeps compression flag
		{data: []byte("after")},
	}
	writeWAL(t, dir, recs)
	got, st := readAll(t, dir)
	if st.Kept != 3 || st.Dropped != 0 || st.BadFragments != 0 {
		t.Fatalf("unexpected stats %+v", st)
	}
	for i := range recs {
		if got[i].flags != recs[i].flags || !bytes.Equal(got[i].data, recs[i].data) {
			t.Fatalf("record %d mismatch", i)
		}
	}
}

func TestCorruptPageDropsOnlyAffectedRecords(t *testing.T) {
	dir := t.TempDir()
	var recs []record
	// Fill several pages with small records, then corrupt a byte in the second page.
	for i := 0; i < 2000; i++ {
		recs = append(recs, record{data: bytes.Repeat([]byte{byte(i)}, 100)})
	}
	writeWAL(t, dir, recs)
	seg := filepath.Join(dir, "00000000")
	b, err := os.ReadFile(seg)
	if err != nil {
		t.Fatal(err)
	}
	b[pageSize+500] ^= 0xff
	if err := os.WriteFile(seg, b, 0o644); err != nil {
		t.Fatal(err)
	}
	got, st := readAll(t, dir)
	if st.BadFragments != 1 {
		t.Fatalf("expected 1 bad fragment, got %+v", st)
	}
	// Only the rest of the corrupted page is lost, far fewer than all later records.
	lost := len(recs) - len(got)
	if lost == 0 || lost > pageSize/100 {
		t.Fatalf("expected to lose part of one page of records, lost %d", lost)
	}
	if !bytes.Equal(got[len(got)-1].data, recs[len(recs)-1].data) {
		t.Fatal("records after the corruption were not recovered")
	}
}

func TestKeepsCheckpointAndSegmentNumbers(t *testing.T) {
	in, out := t.TempDir(), t.TempDir()
	writeSegment(t, filepath.Join(in, "checkpoint.00000004", "00000000"), []record{{data: []byte("series")}})
	writeSegment(t, filepath.Join(in, "00000005"), []record{{data: []byte("five")}})
	writeSegment(t, filepath.Join(in, "00000006"), []record{{data: []byte("six")}})
	writeSegment(t, filepath.Join(in, "checkpoint.00000006.tmp", "00000000"), []record{{data: []byte("partial")}})
	st, err := repair(in, out, nil)
	if err != nil {
		t.Fatal(err)
	}
	if st.Kept != 3 {
		t.Fatalf("unexpected stats %+v", st)
	}
	for path, want := range map[string]string{
		"checkpoint.00000004/00000000": "series",
		"00000005":                     "five",
		"00000006":                     "six",
	} {
		b, err := os.ReadFile(filepath.Join(out, path))
		if err != nil {
			t.Fatal(err)
		}
		var got []record
		if err := readSegment(b, &stats{}, func(r record) error { got = append(got, r); return nil }); err != nil {
			t.Fatal(err)
		}
		if len(got) != 1 || string(got[0].data) != want {
			t.Fatalf("%s: got %v, want %q", path, got, want)
		}
	}
	if _, err := os.Stat(filepath.Join(out, "checkpoint.00000006.tmp")); !os.IsNotExist(err) {
		t.Fatal("unfinished checkpoint should be skipped")
	}
}

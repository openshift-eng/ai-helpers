// walfix rewrites a Prometheus WAL directory, keeping every record whose fragments pass
// their CRC check and dropping corrupt ones.
//
// Prometheus snapshots gathered from CI jobs are copied from a running server and often
// contain a corrupt page early in the WAL. On startup Prometheus "repairs" this by
// deleting every segment after the corruption, which silently throws away most of the
// run's data. walfix instead skips the corrupt fragments, resyncs at the next page and
// writes a clean WAL that Prometheus can replay. Each input segment, including those in
// checkpoint directories, becomes an output segment with the same name.
//
// Usage: walfix <input-wal-dir> <output-wal-dir>
package main

import (
	"encoding/binary"
	"fmt"
	"hash/crc32"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const (
	pageSize    = 32 * 1024
	hdrSize     = 7
	recPageTerm = 0
	recFull     = 1
	recFirst    = 2
	recMiddle   = 3
	recLast     = 4
	typeMask    = 0x7
)

var castagnoli = crc32.MakeTable(crc32.Castagnoli)

type record struct {
	flags byte // compression flags (upper bits of the type byte)
	data  []byte
}

type stats struct {
	Kept, Dropped, BadFragments int
}

// writer writes records into a single WAL segment file.
type writer struct {
	f    *os.File
	page []byte
}

func newWriter(path string) (*writer, error) {
	f, err := os.Create(path)
	if err != nil {
		return nil, err
	}
	return &writer{f: f}, nil
}

// flushPage writes the current page, zero-padded to the full page size.
func (w *writer) flushPage() error {
	if len(w.page) == 0 {
		return nil
	}
	buf := make([]byte, pageSize)
	copy(buf, w.page)
	if _, err := w.f.Write(buf); err != nil {
		return err
	}
	w.page = w.page[:0]
	return nil
}

func (w *writer) close() error {
	if err := w.flushPage(); err != nil {
		return err
	}
	return w.f.Close()
}

func (w *writer) log(r record) error {
	data := r.data
	first := true
	for {
		if pageSize-len(w.page) < hdrSize+1 {
			if err := w.flushPage(); err != nil {
				return err
			}
		}
		n := min(len(data), pageSize-len(w.page)-hdrSize)
		last := n == len(data)
		var typ byte
		switch {
		case first && last:
			typ = recFull
		case first:
			typ = recFirst
		case last:
			typ = recLast
		default:
			typ = recMiddle
		}
		h := make([]byte, hdrSize)
		h[0] = typ | r.flags
		binary.BigEndian.PutUint16(h[1:], uint16(n))
		binary.BigEndian.PutUint32(h[3:], crc32.Checksum(data[:n], castagnoli))
		w.page = append(w.page, h...)
		w.page = append(w.page, data[:n]...)
		data = data[n:]
		first = false
		if last {
			return nil
		}
	}
}

// readSegment calls emit for every intact record in a WAL segment. A fragment that fails
// its CRC drops the record it belongs to, and reading resumes at the next page.
func readSegment(b []byte, st *stats, emit func(record) error) error {
	var cur []byte
	var curFlags byte
	inRec := false
	abandon := func() {
		if inRec {
			st.Dropped++
		}
		inRec, cur = false, nil
	}
	for p := 0; p < len(b); p += pageSize {
		end := min(p+pageSize, len(b))
		off := p
		for off+hdrSize <= end {
			t := b[off]
			typ := t & typeMask
			if typ == recPageTerm {
				break // rest of the page is padding
			}
			n := int(binary.BigEndian.Uint16(b[off+1:]))
			crc := binary.BigEndian.Uint32(b[off+3:])
			if typ > recLast || off+hdrSize+n > end || crc32.Checksum(b[off+hdrSize:off+hdrSize+n], castagnoli) != crc {
				st.BadFragments++
				abandon()
				break // resync at the next page
			}
			frag := b[off+hdrSize : off+hdrSize+n]
			off += hdrSize + n
			switch typ {
			case recFull:
				abandon()
				if err := emit(record{flags: t &^ typeMask, data: append([]byte(nil), frag...)}); err != nil {
					return err
				}
				st.Kept++
			case recFirst:
				abandon()
				cur, curFlags, inRec = append([]byte(nil), frag...), t&^typeMask, true
			case recMiddle:
				if inRec {
					cur = append(cur, frag...)
				}
			case recLast:
				if inRec {
					if err := emit(record{flags: curFlags, data: append(cur, frag...)}); err != nil {
						return err
					}
					st.Kept++
				}
				inRec, cur = false, nil
			}
		}
	}
	abandon()
	return nil
}

// repairSegments rewrites every numbered segment in "in" to a segment with the same name in
// "out". Names are kept because Prometheus replays the segments after the checkpoint by index.
func repairSegments(in, out string, st *stats, progress func(segment string, st stats)) error {
	names, err := filepath.Glob(filepath.Join(in, "[0-9]*"))
	if err != nil {
		return err
	}
	sort.Strings(names)
	if err := os.MkdirAll(out, 0o755); err != nil {
		return err
	}
	for _, name := range names {
		b, err := os.ReadFile(name)
		if err != nil {
			return err
		}
		w, err := newWriter(filepath.Join(out, filepath.Base(name)))
		if err != nil {
			return err
		}
		if err := readSegment(b, st, w.log); err != nil {
			w.f.Close()
			return err
		}
		if err := w.close(); err != nil {
			return err
		}
		if progress != nil {
			rel, _ := filepath.Rel(in, name)
			progress(filepath.Join(filepath.Base(in), rel), *st)
		}
	}
	return nil
}

// repair rewrites the WAL segments and any checkpoints. A checkpoint holds the series records
// for everything created before the last head truncation; without it, samples in later
// segments that refer to those series are dropped on replay.
func repair(in, out string, progress func(segment string, st stats)) (stats, error) {
	var st stats
	checkpoints, err := filepath.Glob(filepath.Join(in, "checkpoint.*"))
	if err != nil {
		return st, err
	}
	for _, cp := range checkpoints {
		if strings.HasSuffix(cp, ".tmp") {
			continue // an unfinished checkpoint, which Prometheus deletes on startup
		}
		if err := repairSegments(cp, filepath.Join(out, filepath.Base(cp)), &st, progress); err != nil {
			return st, err
		}
	}
	return st, repairSegments(in, out, &st, progress)
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: walfix <input-wal-dir> <output-wal-dir>")
		os.Exit(2)
	}
	st, err := repair(os.Args[1], os.Args[2], func(seg string, st stats) {
		fmt.Printf("segment %s: kept=%d dropped=%d badFragments=%d (cumulative)\n", seg, st.Kept, st.Dropped, st.BadFragments)
	})
	if err != nil {
		fmt.Fprintln(os.Stderr, "walfix:", err)
		os.Exit(1)
	}
	fmt.Printf("done: kept=%d dropped=%d badFragments=%d\n", st.Kept, st.Dropped, st.BadFragments)
}

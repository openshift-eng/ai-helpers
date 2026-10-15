// walfix rewrites a Prometheus WAL directory, keeping every record whose fragments pass
// their CRC check and dropping corrupt ones.
//
// Prometheus snapshots gathered from CI jobs are copied from a running server and often
// contain a corrupt page early in the WAL. On startup Prometheus "repairs" this by
// deleting every segment after the corruption, which silently throws away most of the
// run's data. walfix instead skips the corrupt fragments, resyncs at the next page and
// writes a clean WAL that Prometheus can replay.
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
)

const (
	pageSize    = 32 * 1024
	segmentSize = 128 * 1024 * 1024
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

type writer struct {
	dir      string
	seg      int
	f        *os.File
	segBytes int
	page     []byte
}

func newWriter(dir string) (*writer, error) {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, err
	}
	w := &writer{dir: dir}
	return w, w.open()
}

func (w *writer) open() error {
	f, err := os.Create(filepath.Join(w.dir, fmt.Sprintf("%08d", w.seg)))
	if err != nil {
		return err
	}
	w.f, w.segBytes, w.page = f, 0, w.page[:0]
	return nil
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
	w.segBytes += pageSize
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
	// Records must not span segments, so cut a new segment if this one may not fit.
	need := len(r.data) + hdrSize*(len(r.data)/(pageSize-hdrSize)+2)
	if w.segBytes+len(w.page)+need > segmentSize {
		if err := w.close(); err != nil {
			return err
		}
		w.seg++
		if err := w.open(); err != nil {
			return err
		}
	}
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

func repair(in, out string, progress func(segment string, st stats)) (stats, error) {
	var st stats
	names, err := filepath.Glob(filepath.Join(in, "[0-9]*"))
	if err != nil {
		return st, err
	}
	sort.Strings(names)
	w, err := newWriter(out)
	if err != nil {
		return st, err
	}
	for _, name := range names {
		b, err := os.ReadFile(name)
		if err != nil {
			return st, err
		}
		if err := readSegment(b, &st, w.log); err != nil {
			return st, err
		}
		if progress != nil {
			progress(filepath.Base(name), st)
		}
	}
	return st, w.close()
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

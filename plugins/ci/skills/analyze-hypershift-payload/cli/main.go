package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/api"
	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/collect"
	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/history"
	"github.com/openshift-eng/ai-helpers/plugins/ci/skills/analyze-hypershift-payload/cli/internal/report"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	if err := run(ctx, os.Args[1:]); err != nil && !errors.Is(err, flag.ErrHelp) {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(ctx context.Context, args []string) error {
	root := flag.NewFlagSet("analyze-hypershift-payload", flag.ContinueOnError)
	root.Usage = func() {
		fmt.Fprintln(root.Output(), "Usage: analyze-hypershift-payload {collect|report} [options]")
	}
	if err := root.Parse(args); err != nil {
		return err
	}
	switch root.Arg(0) {
	case "collect":
		return collectCommand(ctx, root.Args()[1:])
	case "report":
		return reportCommand(root.Args()[1:])
	default:
		root.Usage()
		return errors.New("expected collect or report")
	}
}

func collectCommand(ctx context.Context, args []string) error {
	flags := flag.NewFlagSet("collect", flag.ContinueOnError)
	out := flags.String("out", "", "destination snapshot JSON file")
	maxPredecessors := flags.Int("max-predecessors", 19, "maximum earlier payloads to collect (0 collects only the target)")
	flags.Usage = func() {
		fmt.Fprintln(flags.Output(), "Usage: collect [-max-predecessors N] -out SNAPSHOT.json TAG")
		flags.PrintDefaults()
	}
	if err := flags.Parse(args); err != nil {
		return err
	}
	if flags.NArg() != 1 || *out == "" {
		return errors.New("collect requires -out and a HyperShift payload tag")
	}
	if *maxPredecessors < 0 {
		return errors.New("-max-predecessors must be nonnegative")
	}
	client := &http.Client{Timeout: 60 * time.Second}
	policy := history.Policy{MaxPredecessors: *maxPredecessors}
	s, err := collect.Snapshot(ctx, collect.Controller{Client: client}, collect.Prow{Client: client}, flags.Arg(0), policy.NeedsPredecessor)
	if err != nil {
		return err
	}
	return writeFile(*out, func(w io.Writer) error {
		encoder := json.NewEncoder(w)
		encoder.SetIndent("", "  ")
		return encoder.Encode(s)
	})
}

func reportCommand(args []string) error {
	flags := flag.NewFlagSet("report", flag.ContinueOnError)
	snapshot := flags.String("snapshot", "", "collected snapshot JSON file")
	findings := flags.String("findings", "", "investigator findings JSON file")
	out := flags.String("out", "", "destination HTML report")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if flags.NArg() != 0 || *snapshot == "" || *findings == "" || *out == "" {
		return errors.New("report requires -snapshot, -findings and -out")
	}
	var s api.Snapshot
	var f api.Findings
	if err := readJSON(*snapshot, &s); err != nil {
		return err
	}
	if err := readJSON(*findings, &f); err != nil {
		return err
	}
	if err := f.ValidateAgainst(s); err != nil {
		return err
	}
	r := api.Report{Snapshot: s, Findings: f}
	return writeFile(*out, func(w io.Writer) error { return report.Render(w, r) })
}

func readJSON(path string, value any) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	d := json.NewDecoder(f)
	d.DisallowUnknownFields()
	if err := d.Decode(value); err != nil {
		return fmt.Errorf("%s: %w", path, err)
	}
	if err := d.Decode(new(any)); err != io.EOF {
		return fmt.Errorf("%s: trailing JSON input", path)
	}
	return nil
}

// Publish only complete artifacts, including when replacing a previous output.
func writeFile(path string, write func(io.Writer) error) error {
	f, err := os.CreateTemp(filepath.Dir(path), ".payload-*")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	if err := write(f); err != nil {
		f.Close()
		return err
	}
	if err := f.Close(); err != nil {
		return err
	}
	return os.Rename(f.Name(), path)
}

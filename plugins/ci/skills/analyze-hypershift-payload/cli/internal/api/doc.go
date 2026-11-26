// Package api defines the internal data exchanged by HyperShift payload analysis.
//
// A Snapshot is a portable record of one bounded collection. A subsequent
// collection may observe different results. The investigator starts from the
// saved snapshot and may consult additional sources to answer specific questions.
// Findings own the investigator's judgments and any supplemental evidence.
//
// The report command calls [Findings.ValidateAgainst] before rendering. Replaying
// the same snapshot and findings produces the same report. The adapters own
// controller and Prow wire formats. The template owns presentation.
package api

# Openshift Origin Test Notes

This document discusses important details and nuance for specific tests and testing frameworks in origin.

### Monitor Tests 

Monitor tests are from a framework in origin that allows test code to monitor the cluster under test during e2e testing, then gives them a chance to generate additional junit results after e2e testing completes. These tests are typically used to scan for abnormal things we don't want to see happen during testing. They can analyze a variety of artifacts including intervals and pod and system journal logs. 

As of 4.21 these tests always contain the substring: `[Monitor:foobar]`

### Excessive Watch Request Tests

These tests  are intended to prevent explosive growth in watch requests by operators. They use fixed values in origin for the upper limits, and the test will fail if over this threshold significantly. When this test fails, it typically indicates natural growth in watches by the operator and the limits need to be updated provided the increase is not massive and explainable. Values below 100 are normal and relatively safe. There is a [claude code command](https://github.com/openshift/origin/blob/main/.claude/commands/update-all-operator-watch-request-limits.md) in the origin repo for easily updating them.  Today we update based on the P99 values over the past month, and then allow **double** that amount. (again, we're looking to catch exponential growth) As such this test should no longer fail very often, if it does, it requires careful scrutiny to understand why. 

These tests will contain the string `should not create excessive watch requests`.

Scan all non-vendor .go files for deprecated import paths and
symbols. For each pattern, run the specified grep and report
hits with file:line.

1. "k8s.io/klog" without "/v2" — deprecated since k8s 1.19
   grep -rn '"k8s.io/klog"' --include='*.go' . | grep -v vendor | grep -v '/v2'

2. "io/ioutil" — deprecated since Go 1.16
   grep -rn '"io/ioutil"' --include='*.go' . | grep -v vendor

3. "golang.org/x/exp/maps", "golang.org/x/exp/slices", "golang.org/x/exp/constraints" — promoted to stdlib
   grep -rn '"golang.org/x/exp/\(maps\|slices\|constraints\)' --include='*.go' . | grep -v vendor

4. "k8s.io/utils/pointer" — deprecated, use "k8s.io/utils/ptr"
   grep -rn '"k8s.io/utils/pointer"' --include='*.go' . | grep -v vendor

5. reflect.Ptr — deprecated constant, use reflect.Pointer
   grep -rn 'reflect\.Ptr\b' --include='*.go' . | grep -v vendor

6. "github.com/golang/protobuf" — deprecated
   grep -rn '"github.com/golang/protobuf' --include='*.go' . | grep -v vendor

7. FieldsV1.Raw or FieldsV1{Raw: — use typed FieldsV1 access
   grep -rn 'FieldsV1\.Raw\|FieldsV1{Raw:' --include='*.go' . | grep -v vendor

Report count per pattern. Zero means clean.

Rules: you are read-only — do not edit files. Cite file:line
for each hit.

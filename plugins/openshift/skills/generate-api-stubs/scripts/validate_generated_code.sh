#!/bin/bash
# Validates that code generation succeeded
# Checks for expected generated files and basic compilation
# Returns 0 if all checks pass, 1 otherwise

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

VALIDATION_FAILED=0

echo "Validating generated code..."
echo ""

# Check 1: Deepcopy files exist
echo -n "Checking for deepcopy generated files... "
DEEPCOPY_FILES=$(find . -name 'zz_generated.deepcopy.go' 2>/dev/null | wc -l)
if [ "$DEEPCOPY_FILES" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Found $DEEPCOPY_FILES deepcopy file(s)"
else
    echo -e "${RED}✗${NC} No zz_generated.deepcopy.go files found"
    VALIDATION_FAILED=1
fi

# Check 2: Generated directory exists
echo -n "Checking for generated/ directory... "
if [ -d "generated" ]; then
    echo -e "${GREEN}✓${NC} generated/ directory exists"
else
    echo -e "${YELLOW}⚠${NC} generated/ directory not found (may be expected for some repos)"
fi

# Check 3: Client code
echo -n "Checking for generated clientset... "
if [ -d "generated/clientset" ] || find . -type d -name "clientset" 2>/dev/null | grep -q .; then
    echo -e "${GREEN}✓${NC} Clientset generated"
else
    echo -e "${YELLOW}⚠${NC} No clientset found (may not be required)"
fi

# Check 4: Informers
echo -n "Checking for generated informers... "
if [ -d "generated/informers" ] || find . -type d -name "informers" 2>/dev/null | grep -q .; then
    echo -e "${GREEN}✓${NC} Informers generated"
else
    echo -e "${YELLOW}⚠${NC} No informers found (may not be required)"
fi

# Check 5: Listers
echo -n "Checking for generated listers... "
if [ -d "generated/listers" ] || find . -type d -name "listers" 2>/dev/null | grep -q .; then
    echo -e "${GREEN}✓${NC} Listers generated"
else
    echo -e "${YELLOW}⚠${NC} No listers found (may not be required)"
fi

# Check 6: OpenAPI schema
echo -n "Checking for OpenAPI generated code... "
if find . -name '*openapi_generated.go' 2>/dev/null | grep -q .; then
    echo -e "${GREEN}✓${NC} OpenAPI schema generated"
else
    echo -e "${YELLOW}⚠${NC} No OpenAPI schema found (may not be required)"
fi

# Check 7: Verify generated files are not empty
echo -n "Checking generated files are not empty... "
EMPTY_FILES=$(find . -name 'zz_generated.*.go' -type f -empty 2>/dev/null)
if [ -z "$EMPTY_FILES" ]; then
    echo -e "${GREEN}✓${NC} All generated files have content"
else
    echo -e "${RED}✗${NC} Found empty generated files:"
    echo "$EMPTY_FILES"
    VALIDATION_FAILED=1
fi

# Check 8: Basic Go compilation
echo -n "Checking if generated code compiles... "
if go build ./... > /tmp/validation-build.log 2>&1; then
    echo -e "${GREEN}✓${NC} Code compiles successfully"
else
    echo -e "${RED}✗${NC} Compilation failed"
    echo "Build errors:"
    cat /tmp/validation-build.log
    VALIDATION_FAILED=1
fi

# Check 9: No obvious errors in generated files
echo -n "Checking for import cycles or syntax errors... "
if go list ./... > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} No import cycles detected"
else
    echo -e "${RED}✗${NC} Found import cycles or package errors"
    go list ./... 2>&1 | head -20
    VALIDATION_FAILED=1
fi

# Summary
echo ""
if [ $VALIDATION_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ Validation passed${NC}"
    echo "All generated code checks completed successfully."
    exit 0
else
    echo -e "${RED}✗ Validation failed${NC}"
    echo "Some validation checks did not pass. Review the errors above."
    exit 1
fi

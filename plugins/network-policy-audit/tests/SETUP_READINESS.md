# Setup and Readiness Check

Quick reference for setting up and verifying your environment before running NetworkPolicy Audit Plugin tests.

## Prerequisites

- Python 3.9 or higher
- OpenShift cluster (AWS recommended)
- `oc` CLI installed
- Admin access to cluster

## Complete Setup Commands

Copy and paste these commands in sequence:

### Step 1: Navigate to Plugin Directory

```bash
cd ai-helpers/plugins/network-policy-audit
```

### Step 2: Create and Activate Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your prompt.

### Step 3: Install Dependencies

```bash
pip3 install -r requirements.txt
```

### Step 4: Verify Python Dependencies

```bash
# Check installed packages
pip3 list | grep -E "kubernetes|pyyaml"

# Verify imports
python3 -c "import kubernetes; print('✅ kubernetes:', kubernetes.__version__)"
python3 -c "import yaml; print('✅ pyyaml: OK')"
```

**Expected Output:**
```
✅ kubernetes: 36.0.2
✅ pyyaml: OK
```

### Step 5: Configure Cluster Access

```bash
# Set KUBECONFIG (adjust path to your kubeconfig)
export KUBECONFIG=~/kubeconfig/cluster.kubeconfig

# Verify cluster connection
oc get nodes
oc whoami
oc cluster-info
```

**Expected Output:**
```bash
# oc whoami
system:admin

# oc get nodes
NAME                        STATUS   ROLES    AGE   VERSION
ip-10-0-xx-xx.ec2.internal  Ready    master   1h    v1.35.5
ip-10-0-yy-yy.ec2.internal  Ready    worker   1h    v1.35.5
...

# oc cluster-info
Kubernetes control plane is running at https://api.cluster-xxx.example.com:6443
```

### Step 6: Navigate to Tests Directory

```bash
cd tests
pwd
```

**Expected:** Path ends with `/ai-helpers/plugins/network-policy-audit/tests`

## Readiness Checklist

Before running tests, verify all these items:

### Python Environment

- [ ] Virtual environment created: `venv/` directory exists
- [ ] Virtual environment activated: `(venv)` appears in terminal prompt
- [ ] Dependencies installed: `pip3 list | grep kubernetes` shows version ≥36.0.2
- [ ] Dependencies installed: `pip3 list | grep pyyaml` shows version ≥6.0.3
- [ ] Python imports working: Both `import kubernetes` and `import yaml` succeed

### Cluster Access

- [ ] KUBECONFIG set: `echo $KUBECONFIG` shows path to kubeconfig file
- [ ] KUBECONFIG file exists: `ls -l $KUBECONFIG` shows the file
- [ ] Cluster accessible: `oc whoami` returns your username (not an error)
- [ ] Cluster nodes visible: `oc get nodes` shows cluster nodes
- [ ] Admin access: User has permissions to create/delete namespaces

### Plugin Files

- [ ] Plugin script exists: `ls ../scripts/netpol_analyzer_cli.py` succeeds
- [ ] Plugin runs: `python3 ../scripts/netpol_analyzer_cli.py --help` shows usage
- [ ] Test scripts exist: `ls validation/run_all_tests.sh` succeeds
- [ ] Test scripts executable: `ls -l validation/run_all_tests.sh` shows `-rwxr-xr-x`

### Directory Location

- [ ] In tests directory: `pwd` ends with `/tests`
- [ ] Can see test subdirectories: `ls` shows `validation/` and `integration/`

## Quick Verification Commands

### One-Line Readiness Check

```bash
(venv) $ python3 -c "import kubernetes, yaml; print('✅ Python OK')" && \
         oc whoami &>/dev/null && echo "✅ Cluster OK" && \
         pwd | grep -q "/tests$" && echo "✅ Directory OK" && \
         echo "✅ READY TO RUN TESTS"
```

**Expected Output:**
```
✅ Python OK
✅ Cluster OK
✅ Directory OK
✅ READY TO RUN TESTS
```

### Detailed Verification Script

```bash
#!/bin/bash
echo "=== Environment Readiness Check ==="
echo ""

# Check virtual environment
if [[ "$VIRTUAL_ENV" == *"venv"* ]]; then
    echo "✅ Virtual environment: Activated"
else
    echo "❌ Virtual environment: Not activated"
    exit 1
fi

# Check Python dependencies
if python3 -c "import kubernetes" 2>/dev/null; then
    K8S_VER=$(python3 -c "import kubernetes; print(kubernetes.__version__)")
    echo "✅ kubernetes: ${K8S_VER}"
else
    echo "❌ kubernetes: Not installed"
    exit 1
fi

if python3 -c "import yaml" 2>/dev/null; then
    echo "✅ pyyaml: Installed"
else
    echo "❌ pyyaml: Not installed"
    exit 1
fi

# Check cluster access
if oc whoami &>/dev/null; then
    USER=$(oc whoami)
    echo "✅ Cluster access: Connected as ${USER}"
else
    echo "❌ Cluster access: Not connected"
    exit 1
fi

# Check location
if pwd | grep -q "/tests$"; then
    echo "✅ Directory: In tests/ directory"
else
    echo "❌ Directory: Not in tests/ directory"
    exit 1
fi

# Check test scripts
if [[ -x "./validation/run_all_tests.sh" ]]; then
    echo "✅ Test scripts: Executable and present"
else
    echo "❌ Test scripts: Not found or not executable"
    exit 1
fi

echo ""
echo "✅ ALL CHECKS PASSED - READY TO RUN TESTS"
```

Save as `check_readiness.sh`, make executable, and run:

```bash
chmod +x check_readiness.sh
./check_readiness.sh
```

## Common Issues

### Issue: Virtual environment not activated

**Symptom:**
```bash
$ python3 -c "import kubernetes"
ModuleNotFoundError: No module named 'kubernetes'
```

**Solution:**
```bash
source venv/bin/activate
```

### Issue: KUBECONFIG not set

**Symptom:**
```bash
$ oc whoami
error: Missing or incomplete configuration info
```

**Solution:**
```bash
export KUBECONFIG=/path/to/your/cluster.kubeconfig
```

### Issue: No cluster access

**Symptom:**
```bash
$ oc get nodes
error: You must be logged in to the server (Unauthorized)
```

**Solution:**
```bash
# Login to cluster
oc login <cluster-url> -u <username> -p <password>

# Or verify KUBECONFIG path
ls -l $KUBECONFIG
```

### Issue: Dependencies not installed

**Symptom:**
```bash
$ pip3 list | grep kubernetes
# (no output)
```

**Solution:**
```bash
pip3 install -r requirements.txt
```

### Issue: Wrong directory

**Symptom:**
```bash
$ ./validation/run_all_tests.sh
bash: ./validation/run_all_tests.sh: No such file or directory
```

**Solution:**
```bash
cd ai-helpers/plugins/network-policy-audit/tests
```

## After Setup

Once all checks pass, you're ready to run tests:

```bash
# Run validation tests (~25 seconds)
./validation/run_all_tests.sh

# Run integration tests (~2-4 minutes)
./integration/run_all_integration_tests.sh

# Cleanup
./integration/cleanup.sh
```

## Environment Variables

Key environment variables for testing:

```bash
# Required
export KUBECONFIG=/path/to/cluster.kubeconfig

# Optional (usually not needed)
export KUBECONFIG_PATH=$KUBECONFIG  # Alternative name
export OC_CLI=/usr/local/bin/oc     # Custom oc path
```

## Minimum Requirements

| Component | Minimum | Recommended | Tested |
|-----------|---------|-------------|--------|
| Python | 3.9 | 3.11+ | 3.14.5 |
| kubernetes (pip) | 28.1.0 | 36.0.0+ | 36.0.2 |
| pyyaml (pip) | 6.0 | 6.0.3+ | 6.0.3 |
| OpenShift | 4.12 | 4.14+ | 4.x |
| Kubernetes | 1.25 | 1.28+ | 1.35.5 |

## Summary

**Quick Setup (Copy/Paste):**

```bash
# 1. Setup
cd ai-helpers/plugins/network-policy-audit
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt

# 2. Verify
pip3 list | grep -E "kubernetes|pyyaml"
python3 -c "import kubernetes; print('✅ kubernetes:', kubernetes.__version__)"
python3 -c "import yaml; print('✅ pyyaml: OK')"

# 3. Cluster
export KUBECONFIG=~/kubeconfig/cluster.kubeconfig
oc get nodes
oc whoami
oc cluster-info

# 4. Navigate
cd tests

# 5. Ready!
./validation/run_all_tests.sh
```

---

**Status:** If all commands succeed, you're ready to run tests!

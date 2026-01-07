---
description: Take a comprehensive knowledge assessment to evaluate your understanding of the codebase and frameworks
argument-hint: "[topic]"
---

## Name
myga:assess

## Synopsis
```
/myga:assess [topic]
```

## Description
The `myga:assess` command administers a comprehensive knowledge assessment to evaluate your understanding of the codebase, frameworks, and related technologies. The assessment adapts to your skill level and provides detailed feedback on strengths and areas for improvement.

This command is particularly useful for:
- Identifying knowledge gaps in a new codebase
- Measuring learning progress over time
- Preparing for technical interviews
- Validating understanding before working on critical features
- Getting personalized learning recommendations
- Setting baseline knowledge before onboarding

The assessment includes:
- **Multiple question types**: Multiple choice, code reading, debugging, design
- **Adaptive difficulty**: Questions adjust based on your answers
- **Real code examples**: All questions use actual codebase files
- **Detailed feedback**: Explanations for every answer
- **Skill breakdown**: Granular view of strengths and weaknesses
- **Learning roadmap**: Personalized recommendations based on results

## Implementation

### Phase 1: Assessment Setup

1. **Determine assessment scope**
   - If topic provided: Focus assessment on that topic
   - If no topic: Offer comprehensive assessment or topic selection
   - Check for previous assessments to track progress

2. **Analyze codebase**
   - Scan project structure and files
   - Identify technologies and frameworks in use
   - Detect key components and patterns
   - Build question pool based on actual code

3. **Configure assessment**
   ```
   📊 Assessment Configuration
   
   Topic: Kubernetes Operators
   Questions: 20 (estimated 30 minutes)
   Difficulty: Adaptive (starts Medium)
   
   Question Types:
   - Conceptual: 30%
   - Code Reading: 30%
   - Debugging: 20%
   - Design: 20%
   
   Ready to begin? (yes/no)
   ```

### Phase 2: Question Generation

Generate diverse question types:

1. **Multiple Choice Questions**
   ```
   Question 5 of 20 | Difficulty: Medium
   
   Look at this code from controllers/etcd_controller.go:
   
   func (r *Reconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
       cluster := &etcdv1.EtcdCluster{}
       if err := r.Get(ctx, req.NamespacedName, cluster); err != nil {
           return ctrl.Result{}, client.IgnoreNotFound(err)
       }
       // ... rest of code
   }
   
   What does client.IgnoreNotFound(err) do?
   
   a) Converts 404 errors to nil, passes through other errors
   b) Logs the error and ignores it
   c) Returns the error to be retried
   d) Creates a new resource if not found
   
   Your answer:
   ```

2. **Code Reading Questions**
   ```
   Question 8 of 20 | Difficulty: Medium
   
   Read this function from pkg/storage/cache.go:
   
   [Shows 15-20 lines of actual code]
   
   What is the time complexity of this cache lookup?
   
   a) O(1) average case
   b) O(log n)
   c) O(n)
   d) O(n²)
   
   Explain your reasoning:
   [Free text input]
   ```

3. **Debugging Questions**
   ```
   Question 12 of 20 | Difficulty: Hard
   
   This code from api/handlers.go has a bug:
   
   func (h *Handler) GetUsers(w http.ResponseWriter, r *http.Request) {
       users := []User{}
       for _, id := range userIDs {
           user, err := h.db.GetUser(id)
           if err != nil {
               continue
           }
           users = append(users, user)
       }
       json.NewEncoder(w).Encode(users)
   }
   
   What's the bug and how would you fix it?
   
   [Free text input]
   ```

4. **Design Questions**
   ```
   Question 16 of 20 | Difficulty: Hard
   
   You need to add rate limiting to the API server.
   
   Requirements:
   - 100 requests per minute per client
   - Clients identified by API key
   - Must work with multiple server replicas
   
   Describe your design approach:
   [Free text input]
   
   What data structure would you use?
   [Free text input]
   ```

### Phase 3: Adaptive Testing

1. **Difficulty Adjustment**
   - Start at medium difficulty
   - Track consecutive correct/incorrect answers
   - 3 consecutive correct → Increase difficulty
   - 2 consecutive incorrect → Decrease difficulty
   - Ensures appropriate challenge level

2. **Topic Coverage**
   - Ensure broad coverage of assessment scope
   - Prioritize important concepts
   - Cover both fundamentals and advanced topics
   - Include project-specific patterns

3. **Response Processing**
   - Evaluate multiple choice immediately
   - For free text: Analyze using code understanding
   - Check for partial credit opportunities
   - Track response time (optional)

### Phase 4: Feedback and Scoring

1. **Immediate Feedback** (per question)
   ```
   ✅ Correct! (2/2 points)
   
   Explanation: client.IgnoreNotFound(err) returns nil if the
   error is a NotFound error, otherwise returns the error unchanged.
   This is idiomatic in controller-runtime because a deleted resource
   is not an error condition during reconciliation.
   
   📚 Learn More: See controller-runtime documentation on error handling
   ```
   
   or
   
   ```
   ❌ Incorrect (0/2 points)
   
   Your answer: b) Logs the error and ignores it
   Correct answer: a) Converts 404 errors to nil, passes through other errors
   
   Explanation: The function specifically checks for NotFound errors
   and converts them to nil. Other errors are returned unchanged, not
   ignored. This pattern is common in Kubernetes controllers.
   
   💡 Review: Kubernetes error handling patterns
   ```

2. **Partial Credit** (for free text)
   ```
   ⚠️ Partial Credit (1.5/2 points)
   
   Your answer identified the goroutine leak correctly ✅
   Your fix would work but isn't idiomatic ⚠️
   You missed the context cancellation issue ❌
   
   Here's a more complete solution...
   ```

3. **Progress Tracking**
   ```
   Progress: [████████░░] 8/20 questions
   Score so far: 14/16 (87.5%)
   Current difficulty: Hard
   Time elapsed: 12 minutes
   ```

### Phase 5: Results and Recommendations

1. **Overall Score**
   ```
   🎯 Assessment Complete!
   
   ═══════════════════════════════════════
   Overall Score: 85% (34/40 points)
   ═══════════════════════════════════════
   
   Time: 28 minutes
   Questions: 20
   Difficulty: Mostly Hard
   
   Percentile: Top 15% (based on typical performance)
   ```

2. **Skill Breakdown**
   ```
   📊 Detailed Breakdown
   
   Conceptual Understanding      ████████░░ 80% (8/10)
   Code Reading                  █████████░ 90% (9/10)
   Debugging                     ███████░░░ 70% (7/10)
   Design & Architecture         ████████░░ 85% (8.5/10)
   
   By Topic:
   ✅ Kubernetes Controllers     ████████░░ 95%
   ✅ Error Handling             ████████░░ 90%
   ⚠️  Concurrency               ██████░░░░ 75%
   ⚠️  Testing Patterns          ██████░░░░ 70%
   ❌ Performance Optimization   ████░░░░░░ 55%
   ```

3. **Strengths and Weaknesses**
   ```
   💪 Strengths
   
   - Excellent understanding of Kubernetes reconciliation loops
   - Strong grasp of error handling patterns
   - Good code reading and comprehension skills
   - Solid understanding of the codebase architecture
   
   📚 Areas for Improvement
   
   - Concurrency patterns (channels, mutexes, race conditions)
     → Recommend: /myga:start "go concurrency"
   
   - Testing strategies (table-driven tests, mocks)
     → Recommend: /myga:challenge "testing"
   
   - Performance optimization (profiling, benchmarking)
     → Recommend: /myga:start "performance optimization"
   ```

4. **Personalized Learning Path**
   ```
   🗺️ Recommended Learning Path
   
   Based on your assessment, here's your personalized roadmap:
   
   📅 Week 1: Strengthen Concurrency
   1. /myga:start "go concurrency patterns"
   2. /myga:challenge "fix race condition"
   3. /myga:challenge "implement worker pool"
   
   📅 Week 2: Master Testing
   1. /myga:start "testing strategies"
   2. /myga:challenge "write table-driven tests"
   3. /myga:challenge "mock external dependencies"
   
   📅 Week 3: Performance Optimization
   1. /myga:start "performance optimization"
   2. /myga:challenge "optimize hot path"
   3. /myga:challenge "reduce allocations"
   
   Use /myga:path to track your progress!
   ```

5. **Save Results**
   - Save to `.work/myga/assessments/<topic>-<timestamp>.json`
   - Include all questions, answers, and scores
   - Track progress over time
   - Enable comparison with previous assessments

### Phase 6: Progress Tracking

1. **Compare with Previous Assessments**
   ```
   📈 Progress Over Time
   
   Kubernetes Operators Assessment
   
   Today:        85% ████████░░
   2 weeks ago:  72% ███████░░░
   1 month ago:  58% ██████░░░░
   
   Improvement: +27 points (46% growth)
   
   Fastest Growing Skills:
   - Error Handling: +35%
   - Code Reading: +28%
   - Debugging: +22%
   ```

2. **Achievement System**
   ```
   🏆 Achievements Unlocked!
   
   🥇 Kubernetes Expert (Score 90%+ on K8s assessment)
   📚 Quick Learner (27% improvement in 1 month)
   🎯 Perfect Round (5 consecutive correct answers)
   ```

## Assessment Types

### Quick Assessment (10 questions, 15 minutes)
- Rapid skill check
- Focused on single topic
- Good for progress tracking

### Standard Assessment (20 questions, 30 minutes)
- Comprehensive topic coverage
- Mix of question types
- Balanced difficulty

### Deep Assessment (40 questions, 60 minutes)
- Exhaustive evaluation
- Advanced topics included
- Detailed skill breakdown

### Diagnostic Assessment (Adaptive length)
- Identifies knowledge gaps
- Stops when sufficient data collected
- Optimizes for learning recommendations

## Return Value

- **Score Report**: Overall score and percentile
- **Skill Breakdown**: Detailed analysis by topic and skill type
- **Question Review**: All questions with your answers and correct answers
- **Learning Recommendations**: Personalized next steps
- **Results File**: `.work/myga/assessments/<topic>-<timestamp>.json`
- **Progress Comparison**: If previous assessments exist

## Examples

### Example 1: Comprehensive assessment

```bash
/myga:assess
```

**Output:**
```
📊 Comprehensive Knowledge Assessment

I'll evaluate your understanding of this codebase and its frameworks.

Detected Technologies:
- Language: Go
- Frameworks: Kubernetes, gRPC, etcd
- Architecture: Microservices, Controllers

Assessment Options:

1. Quick Check (10 questions, 15 min)
   - Fast skill overview
   
2. Standard Assessment (20 questions, 30 min)
   - Comprehensive evaluation
   
3. Deep Dive (40 questions, 60 min)
   - Exhaustive analysis
   
4. Custom (choose topics)

Which would you like? (1-4)
```

### Example 2: Topic-specific assessment

```bash
/myga:assess kubernetes
```

**Output:**
```
🎯 Kubernetes Assessment

This assessment will evaluate your Kubernetes knowledge
in the context of this operator codebase.

Topics Covered:
- Controller patterns
- Resource reconciliation
- Custom Resource Definitions
- Client-go library
- Leader election
- Garbage collection

Questions: 20
Estimated time: 30 minutes
Difficulty: Adaptive (starts Medium)

Ready? (yes/no)

[After completion...]

🎯 Assessment Complete!

Overall Score: 85% (34/40 points)

📊 Kubernetes Skills Breakdown:

Controllers         ████████░░ 95% 🌟
Reconciliation      ████████░░ 90%
CRDs                ████████░░ 85%
Client-go           ███████░░░ 75% ⚠️
Leader Election     ██████░░░░ 65% ⚠️
Garbage Collection  ███████░░░ 80%

💪 Strengths:
- Excellent grasp of reconciliation loop patterns
- Strong understanding of controller architecture

📚 Focus Areas:
- Client-go advanced features (informers, workqueues)
  → /myga:start "client-go deep dive"
  
- Leader election implementation
  → /myga:challenge "implement leader election"

See full report: .work/myga/assessments/kubernetes-2025-12-20.json
```

### Example 3: Progress tracking

```bash
/myga:assess go-concurrency
```

**Output:**
```
🎯 Go Concurrency Assessment

📜 I found previous assessments:
- 1 week ago: 68%
- 2 weeks ago: 55%

Let's see how much you've improved!

[After assessment...]

🎉 Excellent Progress!

Today's Score: 88% (35.5/40 points)

📈 Improvement: +20 points (29% growth in 1 week!)

Skills Improved Most:
- Channels:        55% → 90% (+35%) 🚀
- Mutexes:         60% → 85% (+25%)
- Race Detection:  72% → 90% (+18%)

🏆 Achievement Unlocked: "Concurrency Master"
    (Score 85%+ on concurrency assessment)

You're ready for:
- /myga:challenge "concurrent cache" (Hard)
- /myga:start "advanced concurrency patterns"
```

## Arguments

- **[topic]** *(optional)*
  - If provided: Assess knowledge on specific topic
  - If omitted: Offer comprehensive or custom assessment
  - Examples: `"kubernetes"`, `"testing"`, `"architecture"`

## Prerequisites

- Works in any codebase
- For best results: Have some familiarity with the codebase
- No time limit (but estimated times provided)

## Best Practices

1. **Be honest**: Don't look up answers during assessment
2. **Explain your thinking**: For free-text questions, show your reasoning
3. **Take your time**: Accuracy matters more than speed
4. **Review feedback**: Read explanations for every question
5. **Track progress**: Retake assessments periodically to measure growth
6. **Act on recommendations**: Follow the suggested learning path
7. **Stay calibrated**: Use assessments before and after learning sessions

## Assessment Philosophy

Our assessments are designed to:
- **Teach, not just test**: Every question includes learning value
- **Use real code**: All examples from your actual codebase
- **Be fair**: Questions match concepts you'd actually use
- **Provide value**: Feedback helps you improve, not just score
- **Adapt**: Difficulty adjusts to your level
- **Respect time**: Efficient question selection

## See Also

- `/myga:start` - Interactive learning sessions
- `/myga:challenge` - Hands-on coding challenges  
- `/myga:path` - View complete learning roadmap




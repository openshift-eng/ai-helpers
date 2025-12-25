---
description: View and manage your personalized learning roadmap with progress tracking
argument-hint:
---

## Name
myga:path

## Synopsis
```
/myga:path
```

## Description
The `myga:path` command displays your personalized learning roadmap, showing completed lessons, current progress, and recommended next steps. It provides a comprehensive view of your learning journey across all topics in the codebase.

This command is particularly useful for:
- Visualizing your overall learning progress
- Planning your learning schedule
- Staying motivated with clear goals and milestones
- Identifying which skills to prioritize
- Tracking mastery across multiple topics
- Resuming learning after breaks

The roadmap includes:
- **Visual progress tracking** for each topic
- **Skill mastery levels** (Beginner → Intermediate → Advanced → Expert)
- **Recommended learning sequence** based on dependencies
- **Time estimates** for remaining work
- **Achievement tracking** and milestones
- **Personalized recommendations** based on codebase and assessment results

## Implementation

### Phase 1: Data Collection

1. **Load all learning data**
   - Scan `.work/myga/` for progress files
   - Load completed lessons from `.work/myga/<topic>/progress.json`
   - Load assessment results from `.work/myga/assessments/`
   - Load completed challenges from `.work/myga/challenges/progress.json`

2. **Analyze codebase context**
   - Identify technologies and frameworks in use
   - Determine relevant learning topics
   - Build dependency graph (e.g., "Basic Go" before "Go Concurrency")
   - Suggest topics based on codebase composition

3. **Calculate skill levels**
   - Aggregate data from lessons, challenges, and assessments
   - Compute mastery level per topic (0-100%)
   - Determine skill level: Beginner/Intermediate/Advanced/Expert
   - Identify trending skills (improving/plateaued)

### Phase 2: Roadmap Generation

1. **Build topic hierarchy**
   ```
   Fundamentals
   ├── Go Basics
   ├── Testing Fundamentals
   └── Git Workflows
   
   Frameworks
   ├── Kubernetes Core
   ├── Controller Runtime
   └── gRPC
   
   Architecture
   ├── Microservices Patterns
   ├── Distributed Systems
   └── Observability
   
   Advanced
   ├── Performance Optimization
   ├── Security Hardening
   └── Production Operations
   ```

2. **Determine optimal learning sequence**
   - Respect prerequisite relationships
   - Prioritize foundational topics
   - Consider assessment results (focus on weak areas)
   - Balance breadth and depth
   - Align with codebase needs

3. **Generate recommendations**
   - Suggest next 3-5 topics to learn
   - Explain why each topic matters
   - Provide time estimates
   - Highlight "quick wins" vs "deep dives"

### Phase 3: Visualization

1. **Overall Progress Dashboard**
   ```
   🗺️ Your Learning Roadmap
   ═══════════════════════════════════════════════════════════
   
   📊 Overall Progress: 42% (Level: Intermediate)
   
   🎯 Current Focus: Kubernetes Controllers
   ⏱️  Time invested: 24 hours
   📅 Learning streak: 7 days
   🏆 Achievements: 12
   
   ═══════════════════════════════════════════════════════════
   ```

2. **Topic Progress Grid**
   ```
   📚 Topics by Category
   
   ── Fundamentals ──────────────────────────────────
   ✅ Go Basics                 ██████████ 100% Expert
   ✅ Testing                   ████████░░  85% Advanced
   ⏳ Error Handling            ██████░░░░  65% Intermediate
   🔒 Concurrency               ████░░░░░░  45% Beginner
   
   ── Frameworks ────────────────────────────────────
   ⏳ Kubernetes Core           ███████░░░  72% Intermediate
   ⏳ Controller Runtime         █████░░░░░  58% Intermediate
   🔒 Client-go Advanced        ██░░░░░░░░  25% Beginner
   ⚪ gRPC                      ░░░░░░░░░░   0% Not Started
   
   ── Architecture ──────────────────────────────────
   ⏳ Microservices Patterns    ████░░░░░░  48% Beginner
   🔒 Distributed Systems       ░░░░░░░░░░   0% Locked
   🔒 Observability             ░░░░░░░░░░   0% Locked
   
   ── Advanced ──────────────────────────────────────
   🔒 Performance Optimization  ░░░░░░░░░░   0% Locked
   🔒 Security Hardening        ░░░░░░░░░░   0% Locked
   
   Legend:
   ✅ Completed  ⏳ In Progress  🔒 Locked  ⚪ Available
   ```

3. **Detailed Topic View**
   ```
   📖 Topic Deep Dive: Kubernetes Controllers
   
   Progress: ███████░░░ 72% (Intermediate)
   
   Completed:
   ✅ Controller Pattern Basics        (2 days ago)
   ✅ Reconciliation Loops             (1 day ago)
   ✅ Event Handling                   (1 day ago)
   
   In Progress:
   ⏳ Error Handling & Retries         (50% complete)
      - Next: /myga:start "controller errors"
   
   Not Started:
   ⚪ Leader Election
   ⚪ Finalizers & Garbage Collection
   ⚪ Advanced Patterns
   
   Challenges Completed: 3/7
   Last Assessment: 85% (3 days ago)
   
   Estimated time to mastery: 6-8 hours
   ```

4. **Skills Matrix**
   ```
   🎯 Skills Breakdown
   
                                Beginner  Inter.  Adv.  Expert
   ─────────────────────────────────────────────────────────
   Reading Code                 ████████████████████  ●
   Understanding Architecture   ███████████████░░░░░      ●
   Implementing Features        ██████████████░░░░░░    ●
   Debugging                    █████████████░░░░░░░   ●
   Testing                      ████████████░░░░░░░░  ●
   Performance Analysis         ██████░░░░░░░░░░░░░░ ●
   ```

### Phase 4: Recommendations

1. **Next Steps**
   ```
   🎯 Recommended Next Actions
   
   1. 🔥 Complete Current Topic (HIGH PRIORITY)
      /myga:start "controller errors"
      ⏱️ 45 minutes | Progress: 50% → 75%
      
   2. ⭐ Practice What You Learned
      /myga:challenge "implement retry logic"
      ⏱️ 30 minutes | Reinforces: Error handling
      
   3. 📊 Validate Understanding
      /myga:assess "kubernetes controllers"
      ⏱️ 25 minutes | Unlock: Advanced topics
      
   4. 🚀 Start Next Topic
      /myga:start "leader election"
      ⏱️ 2 hours | Dependency: Controllers (✅)
   ```

2. **Unlock Criteria**
   ```
   🔒 Locked Topics & How to Unlock
   
   Distributed Systems
   ├─ Requires: Kubernetes Controllers (72% ✅)
   ├─ Requires: Concurrency (45% ❌ - need 60%)
   └─ Recommended: Complete /myga:start "go concurrency"
   
   Performance Optimization
   ├─ Requires: Go Basics (100% ✅)
   ├─ Requires: Testing (85% ✅)
   └─ Available to start!
   ```

3. **Learning Goals**
   ```
   🎯 Suggested Goals
   
   This Week:
   [ ] Complete Kubernetes Controllers
   [ ] Reach 60% on Concurrency
   [ ] Complete 2 coding challenges
   
   This Month:
   [ ] Achieve Advanced level in 3 topics
   [ ] Unlock Distributed Systems
   [ ] Complete 10 challenges
   [ ] Assessment score 85%+ on Controllers
   ```

### Phase 5: Analytics and Insights

1. **Learning Analytics**
   ```
   📈 Learning Analytics (Last 30 Days)
   
   Time Invested:     24 hours
   Sessions:          18
   Avg Session:       1.3 hours
   Longest Streak:    7 days (current!)
   Topics Started:    6
   Topics Completed:  1
   
   Most Active:
   - Kubernetes (12 hours)
   - Go (8 hours)
   - Testing (4 hours)
   
   Fastest Growth:
   - Controllers: +35%
   - Error Handling: +28%
   ```

2. **Achievements**
   ```
   🏆 Recent Achievements
   
   🎓 Controller Expert        (Score 90%+ on assessment)
   🔥 Week Streak             (7 consecutive days)
   ⚡ Quick Learner           (+35% in one topic)
   💪 Challenge Master        (Complete 10 challenges)
   
   Next Achievement:
   🌟 Advanced Developer (3 topics at Advanced level)
      Progress: 2/3 topics
   ```

3. **Comparison and Benchmarking**
   ```
   📊 Progress Comparison
   
   Your Progress vs. Typical Learning Path:
   
   Kubernetes Controllers:
   You:      ███████░░░ 72% (8 hours)
   Typical:  █████░░░░░ 55% (8 hours)  [+17% faster!]
   
   Go Concurrency:
   You:      ████░░░░░░ 45% (4 hours)
   Typical:  ██████░░░░ 60% (6 hours)  [Recommend more practice]
   ```

### Phase 6: Export and Sharing

1. **Generate Report**
   ```
   User: "export my progress"
   
   📄 Generating learning report...
   
   Created:
   - .work/myga/reports/learning-report-2025-12-20.md
   - .work/myga/reports/learning-report-2025-12-20.json
   
   You can share this with mentors or use it for:
   - Performance reviews
   - Learning portfolio
   - Team onboarding templates
   ```

2. **Export Format**
   - Markdown summary (human-readable)
   - JSON data (machine-readable)
   - Visual progress charts (if requested)

## Return Value

- **Visual Roadmap**: Comprehensive view of all topics and progress
- **Recommendations**: Personalized next steps
- **Analytics**: Learning statistics and insights
- **Achievements**: Unlocked achievements and next milestones

## Examples

### Example 1: View complete roadmap

```bash
/myga:path
```

**Output:**
```
🗺️ Your Learning Roadmap
═══════════════════════════════════════════════════════════

📊 Overall Progress: 42% (Level: Intermediate)
🎯 Current Focus: Kubernetes Controllers (72%)
⏱️  Time invested: 24 hours across 18 sessions
📅 Learning streak: 7 days 🔥
🏆 Achievements: 12/25

Last activity: 2 hours ago (/myga:start "controller errors")

─────────────────────────────────────────────────────────

📚 Topics Progress

✅ COMPLETED (1)
  Go Basics                    ██████████ 100% Expert

⏳ IN PROGRESS (4)
  Testing                      ████████░░  85% Advanced
  Kubernetes Controllers       ███████░░░  72% Intermediate
  Error Handling               ██████░░░░  65% Intermediate  
  Concurrency                  ████░░░░░░  45% Beginner

⚪ AVAILABLE (3)
  gRPC                         ░░░░░░░░░░   0% Not Started
  Microservices Patterns       ░░░░░░░░░░   0% Not Started
  Performance Optimization     ░░░░░░░░░░   0% Not Started

🔒 LOCKED (5)
  Client-go Advanced           (requires: Controllers 75%)
  Distributed Systems          (requires: Concurrency 60%)
  Observability               (requires: Microservices)
  Security Hardening          (requires: Advanced level)
  Production Operations        (requires: 3 Advanced topics)

─────────────────────────────────────────────────────────

🎯 Recommended Next Actions

1. 🔥 COMPLETE CURRENT: Controller Error Handling
   /myga:start "controller errors"
   ⏱️ 45 min | Completes Controllers topic to 85%

2. ⭐ PRACTICE: Error Handling Challenge
   /myga:challenge "retry logic"
   ⏱️ 30 min | Reinforces learning

3. 📊 ASSESS: Validate Controllers Knowledge
   /myga:assess "kubernetes controllers"
   ⏱️ 25 min | Unlocks advanced topics

4. 🚀 START: Go Concurrency
   /myga:start "go concurrency"
   ⏱️ 2 hrs | Unlocks Distributed Systems

─────────────────────────────────────────────────────────

View detailed topic: /myga:path <topic-name>
Export report: /myga:path export
```

### Example 2: View specific topic details

```bash
/myga:path kubernetes
```

**Output:**
```
📖 Kubernetes Controllers - Detailed View
═══════════════════════════════════════════════════════════

Progress: ███████░░░ 72% (Intermediate)
Started: 5 days ago
Time invested: 12 hours
Last activity: 2 hours ago

─────────────────────────────────────────────────────────

📚 Learning Modules

✅ COMPLETED (3/7)
  1. Controller Pattern Basics      ✅ (2 days ago)
     • Understanding reconciliation
     • Controller architecture
     • Kubernetes client basics
     
  2. Reconciliation Loops           ✅ (1 day ago)
     • Writing reconcile functions
     • Handling resources
     • Status updates
     
  3. Event Handling                 ✅ (1 day ago)
     • Event filtering
     • Watches and triggers
     • Predicate functions

⏳ IN PROGRESS (1/7)
  4. Error Handling & Retries       ⏳ 50%
     • Error types in controllers
     • Retry strategies
     • Exponential backoff
     → Next: /myga:start "controller errors"

⚪ NOT STARTED (3/7)
  5. Leader Election
  6. Finalizers & Garbage Collection
  7. Advanced Patterns & Optimization

─────────────────────────────────────────────────────────

🎯 Challenges

Completed: 3/7
✅ Basic Controller Implementation   (3 days ago, 95%)
✅ Resource Status Updates           (2 days ago, 88%)
✅ Event Filtering                   (1 day ago, 92%)

Available:
⚪ Implement Retry Logic
⚪ Add Leader Election
⚪ Write Finalizer
⚪ Optimize Reconciliation

─────────────────────────────────────────────────────────

📊 Assessments

Last: 3 days ago - 85% ⭐
Previous: 1 week ago - 68%
Improvement: +17%

Skills:
• Reconciliation Loop:  95% ████████████
• Error Handling:       75% ████████░░
• Leader Election:      60% ██████░░░░
• Advanced Patterns:    55% █████░░░░░

Next assessment recommended: After completing Error Handling

─────────────────────────────────────────────────────────

🎯 Recommendations

To reach Advanced (85%):
1. Complete Error Handling module (+8%)
2. Complete Leader Election module (+12%)
3. Pass 2 more challenges (+5%)

Estimated time: 4-5 hours

To reach Expert (95%):
Complete all modules + master-level challenges
Estimated time: 8-10 hours total
```

### Example 3: Export learning report

```bash
/myga:path export
```

**Output:**
```
📄 Exporting Learning Report...

Generated Reports:

📋 Summary Report (Markdown)
   .work/myga/reports/learning-report-2025-12-20.md
   - Overall progress and statistics
   - Topic breakdown with details
   - Achievements and milestones
   - Recommendations

📊 Detailed Data (JSON)
   .work/myga/reports/learning-report-2025-12-20.json
   - Complete learning history
   - Assessment results
   - Challenge solutions
   - Time tracking data

✅ Reports generated successfully!

Use these reports for:
• Performance reviews
• Sharing progress with mentors
• Tracking long-term growth
• Team onboarding templates
```

## Arguments

- None (or optional topic name for detailed view)
  - `/myga:path` - Show complete roadmap
  - `/myga:path <topic>` - Show detailed view of specific topic
  - `/myga:path export` - Export learning report

## Prerequisites

- Some learning activity (sessions, challenges, or assessments)
- For best visualization: Terminal with Unicode support

## Best Practices

1. **Check regularly**: Review your path weekly to stay on track
2. **Follow recommendations**: The AI adapts suggestions to your needs
3. **Balance breadth and depth**: Don't rush through topics
4. **Celebrate progress**: Acknowledge your achievements
5. **Set realistic goals**: Use time estimates to plan learning sessions
6. **Unlock strategically**: Focus on prerequisites for topics you need
7. **Export periodically**: Keep records of your growth

## Roadmap Features

| Feature | Description |
|---------|-------------|
| **Progress Tracking** | Visual indicators for each topic |
| **Skill Levels** | Beginner → Intermediate → Advanced → Expert |
| **Dependencies** | Shows topic prerequisites |
| **Time Estimates** | Projected time to completion |
| **Achievements** | Gamification and milestones |
| **Recommendations** | AI-powered next steps |
| **Analytics** | Learning statistics and trends |
| **Export** | Shareable reports |

## See Also

- `/myga:start` - Start or resume learning sessions
- `/myga:challenge` - Practice with coding challenges
- `/myga:assess` - Take knowledge assessments




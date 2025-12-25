# MYGA Plugin

**Make Yourself Great Again** - Interactive code tutoring and learning commands for mastering codebases and frameworks through adaptive, hands-on education.

## Overview

The MYGA plugin provides a comprehensive learning platform that helps developers master both their specific codebase and the underlying frameworks and technologies. Unlike static documentation, these commands provide interactive, adaptive learning experiences with real-time feedback and personalized progression.

**Key Features:**
- 🎓 **Interactive Learning Sessions** - Step-by-step tutorials adapted to your skill level
- 🎯 **Coding Challenges** - Hands-on practice with realistic tasks from your codebase
- 📊 **Knowledge Assessments** - Comprehensive testing with detailed feedback
- 🗺️ **Learning Roadmaps** - Personalized paths with progress tracking
- 🧠 **Adaptive Difficulty** - Content adjusts based on your responses
- 💡 **Real Code Examples** - All lessons use actual code from your project
- 🏆 **Achievement System** - Gamification to maintain motivation

## Commands

### `/myga:start [topic]`

Start an interactive learning session on a specific topic or get a personalized topic menu based on your codebase.

**Use Cases:**
- Onboard new team members
- Learn new frameworks or technologies
- Master specific subsystems
- Understand architectural patterns

**Examples:**
```bash
# Show topic menu based on codebase analysis
/myga:start

# Learn about Kubernetes operators
/myga:start kubernetes operators

# Understand authentication in this project
/myga:start authentication

# Resume previous session
/myga:start react hooks
```

**Features:**
- Adaptive difficulty based on your answers
- Real code examples from your codebase
- Interactive exercises and knowledge checks
- Progress tracking across sessions
- Socratic teaching method

---

### `/myga:challenge [topic-or-difficulty]`

Get hands-on coding challenges tailored to your codebase for deliberate practice.

**Use Cases:**
- Practice after completing lessons
- Test understanding of concepts
- Build muscle memory for patterns
- Prepare for interviews
- Focus on weak areas

**Examples:**
```bash
# Get recommended challenge
/myga:challenge

# Challenge on specific topic
/myga:challenge kubernetes

# Challenge at specific difficulty
/myga:challenge hard

# Both topic and difficulty
/myga:challenge "error handling" easy
```

**Challenge Types:**
- Feature Implementation
- Bug Fixing
- Code Refactoring
- Performance Optimization
- Test Writing
- Code Reading & Comprehension
- Architectural Design

**Features:**
- Automated test verification
- Progressive hint system
- Detailed solution reviews
- Multiple difficulty levels
- Realistic, codebase-specific tasks

---

### `/myga:assess [topic]`

Take a comprehensive knowledge assessment with detailed feedback and personalized recommendations.

**Use Cases:**
- Identify knowledge gaps
- Measure learning progress
- Validate understanding
- Get personalized learning recommendations
- Set baseline before onboarding

**Examples:**
```bash
# Comprehensive assessment
/myga:assess

# Topic-specific assessment
/myga:assess kubernetes

# Track improvement over time
/myga:assess go-concurrency
```

**Assessment Features:**
- Multiple question types (multiple choice, code reading, debugging, design)
- Adaptive difficulty
- Immediate feedback with explanations
- Detailed skill breakdown
- Progress comparison over time
- Personalized learning recommendations

**Question Types:**
- Conceptual understanding
- Code reading and comprehension
- Debugging challenges
- Architecture and design

---

### `/myga:path`

View your personalized learning roadmap with comprehensive progress tracking.

**Use Cases:**
- Visualize overall progress
- Plan learning schedule
- Stay motivated with clear goals
- Resume after breaks
- Track mastery across topics

**Examples:**
```bash
# View complete roadmap
/myga:path

# View specific topic details
/myga:path kubernetes

# Export learning report
/myga:path export
```

**Features:**
- Visual progress indicators
- Skill mastery levels (Beginner → Expert)
- Topic dependencies and unlock criteria
- Time estimates for completion
- Achievement tracking
- Learning analytics
- Personalized recommendations
- Export reports for sharing

## Learning Workflow

### 1. **Start Learning**
```bash
/myga:start
```
Choose a topic and begin interactive lessons adapted to your level.

### 2. **Practice**
```bash
/myga:challenge
```
Apply what you learned with hands-on coding challenges.

### 3. **Validate**
```bash
/myga:assess
```
Test your understanding with comprehensive assessments.

### 4. **Track Progress**
```bash
/myga:path
```
Monitor your growth and get personalized next steps.

### 5. **Repeat**
Continue the cycle, unlocking new topics as you progress.

## Skill Levels

| Level | Description | Characteristics |
|-------|-------------|-----------------|
| **Beginner** | 0-30% | Learning fundamentals, needs guidance |
| **Intermediate** | 30-70% | Understands basics, building proficiency |
| **Advanced** | 70-90% | Strong grasp, can handle complex tasks |
| **Expert** | 90-100% | Deep mastery, can teach others |

## Learning Topics

Topics are automatically detected based on your codebase:

**Codebase-Specific:**
- Project architecture
- Component interactions
- API design patterns
- Authentication/authorization flows
- Data models and storage
- Deployment and configuration

**Frameworks & Technologies:**
- Detected languages (Go, Python, JavaScript, etc.)
- Frameworks (Kubernetes, React, gRPC, etc.)
- Tools and libraries in use

**General Software Engineering:**
- Design patterns
- Testing strategies
- Performance optimization
- Security best practices
- Debugging techniques
- Production operations

## Data Storage

Learning data is stored locally in `.work/myga/`:

```
.work/myga/
├── <topic>/
│   ├── progress.json              # Topic progress
│   └── sessions/                  # Session history
├── challenges/
│   ├── progress.json              # Challenge completions
│   └── <challenge-id>/            # Challenge workspaces
├── assessments/
│   └── <topic>-<timestamp>.json   # Assessment results
└── reports/
    └── learning-report-*.md       # Exported reports
```

## Best Practices

### For Learners

1. **Be consistent**: Regular short sessions beat occasional long ones
2. **Do the exercises**: Hands-on practice is essential
3. **Ask questions**: Interrupt anytime to clarify concepts
4. **Review regularly**: Revisit completed topics periodically
5. **Track progress**: Check `/myga:path` weekly
6. **Honest assessments**: Don't look up answers during tests
7. **Follow recommendations**: Trust the personalized learning path

### For Teams

1. **Onboarding**: Use `/myga:start` for new team members
2. **Knowledge sharing**: Export reports to identify skill gaps
3. **Continuous learning**: Encourage weekly learning sessions
4. **Pair programming**: Combine with `/myga:challenge` for collaborative practice
5. **Review process**: Use assessments before assigning complex tasks
6. **Documentation**: Export learning paths as onboarding templates

## Achievement System

Unlock achievements to stay motivated:

- 🎓 **Topic Expert** - Score 90%+ on topic assessment
- 🔥 **Week Streak** - 7 consecutive days of learning
- ⚡ **Quick Learner** - 30%+ improvement in one topic
- 💪 **Challenge Master** - Complete 10 challenges
- 🌟 **Advanced Developer** - Reach Advanced level in 3 topics
- 🏆 **Polyglot** - Complete topics in 3+ languages/frameworks

## Integration with Other Plugins

The MYGA plugin complements other ai-helpers plugins:

- **`/jira:solve`** - Learn the codebase while solving issues
- **`/prow-job:analyze-test-failure`** - Learn from test failures
- **`/utils:generate-test-plan`** - Apply testing knowledge

## Prerequisites

- No special requirements - works in any codebase
- For best experience: Run in a Git repository with source code
- Progress is saved locally (no account required)
- No external services or API keys needed

## Examples

### Complete Learning Journey

```bash
# Day 1: Start learning
/myga:start
> Selects "Kubernetes Controllers"
> Completes 3 lessons (60 minutes)

# Day 2: Practice
/myga:challenge kubernetes
> Implements basic controller (45 minutes)
> Reviews exemplary solution

# Day 3: Continue learning
/myga:start "kubernetes controllers"
> Completes 2 more lessons (40 minutes)

# Day 4: More practice
/myga:challenge "controller patterns"
> Fixes buggy reconciliation logic (30 minutes)

# Day 5: Assessment
/myga:assess kubernetes
> Scores 85% (Intermediate → Advanced)
> Gets personalized recommendations

# Day 6: Check progress
/myga:path
> Views roadmap
> 72% complete on Kubernetes Controllers
> Unlocked: Advanced topics
```

### Targeted Skill Development

```bash
# Identify weak area
/myga:assess
> Result: Concurrency is at 45% (weak area)

# Focus on weakness
/myga:start "go concurrency"
> Complete focused lessons

# Practice deliberately
/myga:challenge "concurrency"
/myga:challenge "race conditions"

# Validate improvement
/myga:assess "go concurrency"
> Result: 78% (+33% improvement!)
```

## Tips for Maximum Learning

1. **Spaced Repetition**: Review topics after 1 day, 1 week, 1 month
2. **Active Recall**: Try challenges before reviewing solutions
3. **Deliberate Practice**: Focus on difficult areas, not comfort zones
4. **Teach Others**: Explain concepts to solidify understanding
5. **Apply Immediately**: Use new knowledge in real work
6. **Mix Topics**: Alternate between related topics for better retention
7. **Track Progress**: Regular feedback maintains motivation

## Support and Feedback

- Report issues on the ai-helpers repository
- Suggest new topics or improvements
- Share your learning success stories
- Contribute challenge ideas

## See Also

- **Main README**: `/home/mykastur/forks/ai-helpers/README.md`
- **Plugin Development**: `/home/mykastur/forks/ai-helpers/AGENTS.md`
- **Other Plugins**: Browse `/plugins/` directory

---

**Start your learning journey today!**

```bash
/myga:start
```

**Make Yourself Great Again!** 🚀

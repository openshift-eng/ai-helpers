---
description: Start an interactive learning session on a topic in the current codebase
argument-hint: "[topic]"
---

## Name
myga:start

## Synopsis
```
/myga:start [topic]
```

## Description
The `myga:start` command (Make Yourself Great Again) initiates an interactive, adaptive learning session that teaches you about the current codebase and its underlying frameworks. The command provides a personalized tutorial experience that adapts to your knowledge level and learning pace.

This command is particularly useful for:
- Onboarding new team members to a complex codebase
- Learning new frameworks or technologies used in the project
- Understanding architectural patterns and design decisions
- Mastering specific subsystems or components
- Building deep expertise through hands-on exploration

The learning experience includes:
- **Interactive lessons** with real code examples from the codebase
- **Adaptive difficulty** that adjusts based on your responses
- **Hands-on exercises** using actual project files
- **Knowledge checks** to verify understanding
- **Progress tracking** across multiple sessions
- **Contextual explanations** tied to your specific codebase

## Implementation

### Phase 1: Topic Selection and Discovery

1. **Determine learning topic**
   - If topic provided: Use specified topic
   - If no topic: Present menu of available topics based on codebase analysis:
     ```
     Available learning topics:
     
     📚 Codebase-Specific:
     1. Project Architecture
     2. Core Components (list detected components)
     3. API Design Patterns
     4. Data Flow and State Management
     5. Testing Strategies
     
     🔧 Frameworks and Technologies:
     6. [Detected framework, e.g., React]
     7. [Detected framework, e.g., Kubernetes]
     8. [Detected language, e.g., Go]
     
     💡 Advanced Topics:
     9. Performance Optimization
     10. Security Best Practices
     11. Deployment and Operations
     
     What would you like to learn about? (1-11 or custom topic)
     ```

2. **Analyze codebase context**
   - Scan project files to understand structure
   - Identify relevant files, packages, and modules for the topic
   - Detect frameworks, libraries, and technologies in use
   - Build topic-specific knowledge map

3. **Load topic curriculum**
   - Use myga:start skill to load structured curriculum
   - Adapt curriculum to detected technologies and patterns
   - Prepare interactive examples from actual codebase

### Phase 2: Knowledge Assessment

1. **Initial skill assessment**
   - Ask 2-3 diagnostic questions to gauge current knowledge
   - Questions range from basic to advanced
   - Examples:
     ```
     Let's assess your current knowledge of React hooks:
     
     Question 1: What does the useEffect hook do?
     a) Manages component state
     b) Performs side effects in function components
     c) Connects to Redux store
     d) I'm not sure
     
     [Wait for response and adapt]
     ```

2. **Determine starting level**
   - Beginner: New to the topic
   - Intermediate: Familiar with basics, needs practice
   - Advanced: Experienced, wants deep dive or edge cases

3. **Set learning path**
   - Create personalized sequence of lessons
   - Skip basics if user demonstrates proficiency
   - Focus on gaps in knowledge

### Phase 3: Interactive Learning Session

The session proceeds through structured lessons:

1. **Lesson Structure** (per topic)
   
   **A. Concept Introduction**
   - Explain the concept clearly with analogies
   - Show why it matters in the context of this codebase
   - Display real code examples from the project
   
   **B. Guided Exploration**
   ```
   Let's explore how authentication works in this codebase.
   
   📖 Concept: This project uses JWT tokens for authentication.
   
   📁 Let's look at a real example from the codebase:
   
   [Show code snippet from auth/middleware.go]
   
   ❓ Can you identify where the token is validated? (line number)
   
   [Wait for response]
   
   ✅ Correct! Line 42 validates the token signature.
   OR
   ℹ️  Not quite. Let's break it down...
   ```
   
   **C. Knowledge Check**
   - Ask comprehension questions
   - Provide immediate feedback
   - Offer hints if needed
   
   **D. Hands-On Exercise**
   ```
   🔨 Exercise: Let's modify the authentication logic
   
   Task: Add logging when a token expires
   File: auth/middleware.go
   
   Try implementing this and share your approach.
   
   [Wait for user response or code]
   
   [Provide feedback on their solution]
   ```

2. **Adaptive Progression**
   - Track correct/incorrect responses
   - Adjust difficulty dynamically:
     - 3+ correct → Increase difficulty
     - 2+ incorrect → Review with simpler examples
   - Offer to skip or revisit topics based on confidence

3. **Interactive Dialogue**
   - Encourage questions at any time
   - Provide detailed explanations when requested
   - Offer alternative explanations if concept unclear
   - Use Socratic method to guide discovery

4. **Practical Application**
   - Every concept includes hands-on practice
   - Use actual files from the codebase
   - Propose realistic modifications or debugging tasks
   - Review user solutions constructively

### Phase 4: Session Management

1. **Progress Tracking**
   - Save progress to `.work/learn/<topic>/progress.json`:
     ```json
     {
       "topic": "React Hooks",
       "level": "intermediate",
       "lessons_completed": ["useState", "useEffect"],
       "lessons_in_progress": ["useContext"],
       "score": 0.85,
       "last_session": "2025-12-20T10:30:00Z",
       "next_recommended": "useReducer"
     }
     ```

2. **Session Controls**
   - User can pause: "Let's pause here" or `/myga:pause`
   - User can skip: "Skip this lesson"
   - User can ask for help: "I don't understand" or "Explain more"
   - User can end: "Stop" or "Exit"

3. **Completion and Next Steps**
   ```
   🎉 Great work! You've completed the React Hooks basics module.
   
   📊 Session Summary:
   - Lessons completed: 5/5
   - Accuracy: 92%
   - Time: 45 minutes
   - Level: Intermediate → Advanced
   
   ✅ You now understand:
   - useState for state management
   - useEffect for side effects
   - useContext for global state
   - Custom hooks patterns
   
   🎯 Recommended Next Steps:
   1. /myga:start "Advanced Hooks Patterns"
   2. /myga:challenge "Build a custom hook"
   3. /myga:path to see your complete learning roadmap
   
   Progress saved to: .work/myga/react-hooks/progress.json
   ```

### Phase 5: Contextual Learning

Throughout the session:

1. **Use Real Code Examples**
   - All examples pulled from actual codebase
   - Explain why code was written this way
   - Discuss alternatives and tradeoffs

2. **Connect to Architecture**
   - Show how concepts fit into overall system
   - Explain design decisions
   - Reference related components

3. **Highlight Best Practices**
   - Point out well-written code in the project
   - Explain anti-patterns to avoid
   - Share team conventions and style

4. **Bridge Theory and Practice**
   - Don't just teach framework concepts
   - Show how they're applied in this specific project
   - Relate to real problems the codebase solves

## Return Value

- **Interactive Learning Session**: Multi-turn conversation with lessons, questions, and exercises
- **Progress File**: `.work/myga/<topic>/progress.json`
- **Session Summary**: Completion status, accuracy, topics covered, and recommendations

## Examples

### Example 1: Start learning with topic menu

```bash
/myga:start
```

**Output:**
```
📚 Welcome to Interactive Learning!

I've analyzed your codebase and found these learning opportunities:

📁 Your Project Stack:
- Language: Go
- Frameworks: Kubernetes, gRPC
- Architecture: Microservices

Available Topics:

📚 Codebase-Specific:
1. Project Architecture Overview
2. Authentication & Authorization Flow
3. gRPC Service Patterns
4. Kubernetes Controllers
5. Error Handling & Logging

🔧 Frameworks:
6. Kubernetes Operators Deep Dive
7. Go Concurrency Patterns
8. gRPC Best Practices

💡 Advanced:
9. Performance Optimization
10. Distributed System Debugging

What would you like to learn? (1-10 or describe a custom topic)
```

### Example 2: Start with specific topic

```bash
/myga:start kubernetes operators
```

**Output:**
```
🎓 Starting: Kubernetes Operators

Let me quickly assess your current knowledge...

❓ Question 1: What is a Kubernetes Operator?

a) A person who manages Kubernetes clusters
b) A pattern for encoding operational knowledge in software
c) A kubectl plugin
d) I'm not familiar with Operators

[After assessment...]

Great! I can see you have some familiarity with the basics.
We'll start at the Intermediate level.

📖 Lesson 1: Operator Pattern in Your Codebase

This project implements a custom operator for managing etcd clusters.
Let's explore how it works...

[Shows code from controllers/etcd_controller.go]

The reconciliation loop is the heart of the operator. Can you 
identify where the reconciliation happens in this file?

[Interactive session continues...]
```

### Example 3: Resume previous session

```bash
/myga:start react hooks
```

**Output:**
```
👋 Welcome back!

I found a previous learning session:
- Topic: React Hooks
- Progress: 3/5 lessons completed (60%)
- Last session: 2 days ago
- Next up: useContext Hook

Would you like to:
1. Continue from where you left off (useContext)
2. Review previous lessons
3. Start over from the beginning

Your choice?
```

### Example 4: Interactive session example

```bash
/myga:start "error handling in Go"
```

**Output:**
```
🎓 Starting: Error Handling in Go

📖 Lesson 1: Error Basics

In Go, errors are values. Let's look at how this project handles errors.

[Shows code from pkg/storage/storage.go:45-52]

func (s *Storage) Get(key string) ([]byte, error) {
    data, err := s.db.Get(key)
    if err != nil {
        return nil, fmt.Errorf("failed to get key %s: %w", key, err)
    }
    return data, nil
}

❓ What does the %w verb do in fmt.Errorf?

> [User types: "It wraps the error"]

✅ Correct! The %w verb wraps the original error, allowing it to be
unwrapped later with errors.Unwrap(). This is crucial for error chains.

Let's explore why error wrapping matters...

[Session continues with more examples and exercises...]

🔨 Exercise: Fix this error handling code

[Shows buggy code]

What's wrong with this error handling? Try to fix it.

> [User responds with fix]

💡 Good thinking! You caught the main issue. Here's one more consideration...

[Provides detailed feedback and continues...]
```

## Arguments

- **[topic]** *(optional)*
  - If omitted: Display menu of available topics based on codebase analysis
  - If provided: Start learning session on the specified topic
  - Examples: `"kubernetes"`, `"authentication"`, `"react hooks"`, `"api design"`

## Prerequisites

- None - works in any codebase
- For best experience: Run in a Git repository with source code
- Progress is saved locally (no account required)

## Best Practices

1. **Take your time**: Learning is most effective when not rushed
2. **Ask questions**: Interrupt with questions anytime
3. **Do the exercises**: Hands-on practice solidifies understanding
4. **Multiple sessions**: Break learning into digestible chunks
5. **Review regularly**: Use `/learn:start` to review completed topics
6. **Connect concepts**: Ask how topics relate to each other
7. **Experiment**: Try modifying code examples in your editor

## Session Commands

During a learning session, you can:
- **Ask questions**: "Why is this done this way?"
- **Request clarification**: "Explain that again" or "Give me another example"
- **Skip ahead**: "I understand this, next lesson"
- **Go back**: "I need to review X"
- **Pause**: "Let's pause" (progress is saved)
- **Exit**: "Stop" or "Exit"
- **Check progress**: "How am I doing?"

## See Also

- `/myga:challenge` - Get coding challenges to practice
- `/myga:assess` - Comprehensive knowledge assessment
- `/myga:path` - View your complete learning roadmap
- `/jira:generate-feature-doc` - Generate documentation from features




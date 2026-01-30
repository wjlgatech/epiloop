---
name: brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation."
---

# Brainstorming Ideas Into Designs

## Overview

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design in small sections (200-300 words), checking after each section whether it looks right so far.

## The Process

**Understanding the idea:**
- Check out the current project state first (files, docs, recent commits)
- Ask questions one at a time to refine the idea
- Prefer multiple choice questions when possible, but open-ended is fine too
- Only one question per message - if a topic needs more exploration, break it into multiple questions
- Focus on understanding: purpose, constraints, success criteria

**Exploring approaches:**
- Propose 2-3 different approaches with trade-offs
- Present options conversationally with your recommendation and reasoning
- Lead with your recommended option and explain why

**Presenting the design:**
- Once you believe you understand what you're building, present the design
- Break it into sections of 200-300 words
- Ask after each section whether it looks right so far
- Cover: architecture, components, data flow, error handling, testing
- Be ready to go back and clarify if something doesn't make sense

## After the Design

**Documentation:**
- Write the validated design to `docs/plans/YYYY-MM-DD-<topic>-design.md`
- Include: overview, architecture, components, implementation steps, testing strategy
- Commit the design document to git

**Implementation (if continuing):**
- Ask: "Ready to generate PRD from this design?"
- Use claude-loop's dynamic PRD generation: `./claude-loop.sh --dynamic "design summary"`
- Or manually create PRD based on design sections

## Integration with claude-loop

**When brainstorming is mandatory:**
- Stories with `estimatedComplexity: "complex"`
- Stories with complexity >= 5
- Design or architecture keywords detected
- User explicitly requests design exploration

**After brainstorming:**
- Design document in `docs/plans/`
- Ready for PRD generation
- Ready for implementation planning

## Key Principles

- **One question at a time** - Don't overwhelm with multiple questions
- **Multiple choice preferred** - Easier to answer than open-ended when possible
- **YAGNI ruthlessly** - Remove unnecessary features from all designs
- **Explore alternatives** - Always propose 2-3 approaches before settling
- **Incremental validation** - Present design in sections, validate each
- **Be flexible** - Go back and clarify when something doesn't make sense

## Example Workflow

```
User: "Add user authentication to the app"

Claude (Understanding):
"Let me understand the requirements. Which authentication method would you prefer?
A) Email/password (traditional, simple)
B) OAuth (Google/GitHub, easier for users)
C) Magic links (passwordless, modern)

What's your preference?"

User: "B - OAuth with Google"

Claude (Exploring):
"Great! For OAuth integration, I see 2 main approaches:

**Approach 1: Library-based (Recommended)**
Use established library (Passport.js, NextAuth, etc.)
+ Faster implementation
+ Well-tested security
- Less customization

**Approach 2: Manual OAuth flow**
Build OAuth flow from scratch
+ Full control
+ Learn OAuth internals
- More security considerations
- Longer development time

I recommend Approach 1 for reliability. Thoughts?"

User: "Yes, Approach 1"

Claude (Design - Section 1):
"**Authentication Architecture**

The system will use Passport.js with Google OAuth strategy. Here's the flow:

1. User clicks 'Login with Google'
2. Redirect to Google consent screen
3. Google redirects back with auth code
4. Exchange code for access token
5. Fetch user profile from Google
6. Create/update user in database
7. Issue JWT session token
8. Store JWT in httpOnly cookie

Components needed:
- Auth routes (/auth/google, /auth/google/callback)
- Passport configuration
- User model with Google ID
- JWT token service

Does this architecture make sense so far?"

User: "Yes, continue"

Claude (Design - Sections 2-4):
[Continues with data flow, error handling, testing sections]

Claude (After validation):
"Design complete! I'll save this to docs/plans/2026-01-15-oauth-authentication-design.md

[Saves and commits design]

Ready to generate PRD from this design? I can create a structured PRD with user stories based on these components."
```

## Tips for Effective Brainstorming

**For simple features:**
- Fewer questions (2-3)
- Quicker validation
- Focus on key decisions

**For complex features:**
- More exploration (4-6 questions)
- Alternative approaches mandatory
- Thorough validation per section
- Consider edge cases early

**Red flags:**
- Jumping to implementation without understanding
- Proposing only one approach (always show alternatives)
- Asking multiple questions in one message
- Presenting entire design at once (break into sections)
- Not validating understanding (ask after each section)

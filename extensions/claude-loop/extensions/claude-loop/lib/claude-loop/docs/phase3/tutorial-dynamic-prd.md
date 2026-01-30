# Tutorial: Dynamic PRD Generation

This tutorial teaches you how to generate complete PRDs from natural language project descriptions using Claude AI.

## Learning Objectives

By the end of this tutorial, you'll be able to:

- Generate PRDs from high-level goals
- Understand how Claude decomposes goals into user stories
- Refine generated PRDs for your needs
- Leverage codebase analysis for better file scope predictions
- Iterate on generated PRDs before execution

**Time Required:** 15-25 minutes

## Tutorial Scenario

You want to add a comment system to your blog application. Instead of manually writing out 8-10 user stories with acceptance criteria, you'll use Dynamic PRD Generation to create the plan automatically.

## Step 1: Write Your Goal

Start by clearly describing what you want to build. The more specific you are, the better the generated PRD will be.

**Good Example:**
```
Add a comment system for blog posts with:
- Users can post comments on blog posts
- Comment threading (replies to comments)
- Moderation tools (approve/reject/delete)
- Email notifications for comment replies
- Markdown support in comments
```

**Better Example:**
```
Implement a comment system for the blog with the following features:

1. Core Commenting:
   - Users can post comments on published blog posts
   - Comments support Markdown formatting
   - Comments include author name, email, timestamp

2. Threading:
   - Users can reply to existing comments
   - Support up to 3 levels of nesting
   - Display replies in chronological order

3. Moderation:
   - Admin dashboard to review pending comments
   - Approve, reject, or delete comments
   - Flag comments as spam

4. Notifications:
   - Email notification when someone replies to your comment
   - Daily digest for blog authors with new comments
   - Configurable notification preferences

Technical constraints:
- Use PostgreSQL for comment storage
- Integrate with existing user authentication
- REST API for comment operations
```

## Step 2: Generate the PRD

Run the dynamic generation command with your goal:

```bash
./claude-loop.sh --dynamic "$(cat <<'EOF'
Implement a comment system for the blog with the following features:

1. Core Commenting:
   - Users can post comments on published blog posts
   - Comments support Markdown formatting
   - Comments include author name, email, timestamp

2. Threading:
   - Users can reply to existing comments
   - Support up to 3 levels of nesting
   - Display replies in chronological order

3. Moderation:
   - Admin dashboard to review pending comments
   - Approve, reject, or delete comments
   - Flag comments as spam

4. Notifications:
   - Email notification when someone replies to your comment
   - Daily digest for blog authors with new comments
   - Configurable notification preferences

Technical constraints:
- Use PostgreSQL for comment storage
- Integrate with existing user authentication
- REST API for comment operations
EOF
)"
```

**Enable codebase analysis for better results:**
```bash
./claude-loop.sh --dynamic "Your goal here" --codebase-analysis
```

## Step 3: Watch Claude Analyze Your Goal

You'll see Claude working through the decomposition:

```
=== Analyzing Goal ===
Goal: Implement a comment system for the blog...

[Claude is thinking...]

Identified components:
✓ Database schema (Comment model)
✓ API endpoints (CRUD operations)
✓ Threading logic (parent-child relationships)
✓ Moderation interface (admin tools)
✓ Email notification system
✓ Frontend integration

Analyzing dependencies...
✓ Comment model must be created before API
✓ API must exist before moderation tools
✓ Moderation tools before notifications

Analyzing codebase structure...
✓ Found existing models in: lib/models/
✓ Found API routes in: lib/api/routes/
✓ Found frontend in: frontend/src/
✓ Found email templates in: templates/email/

Generating user stories...
```

## Step 4: Review Generated PRD

Claude will generate a complete PRD with 8 user stories:

```json
{
  "project": "blog-comment-system",
  "branchName": "feature/blog-comment-system",
  "description": "Implement a comment system for the blog with threading, moderation, and notifications",
  "userStories": [
    {
      "id": "US-001",
      "title": "Comment Database Schema and Model",
      "description": "As a developer, I want to create the Comment model and database schema so that comments can be stored persistently",
      "priority": 1,
      "acceptanceCriteria": [
        "Create Comment model with fields: id, post_id, author_id, parent_comment_id, content, status (pending/approved/rejected/spam), created_at, updated_at",
        "Create database migration for comments table",
        "Add foreign key constraints to blog_posts and users tables",
        "Add index on post_id and parent_comment_id for query performance",
        "Write unit tests for Comment model validations"
      ],
      "passes": false,
      "notes": "",
      "fileScope": [
        "lib/models/comment.py",
        "migrations/XXXX_create_comments.py",
        "tests/models/test_comment.py"
      ],
      "estimatedComplexity": "simple",
      "dependencies": [],
      "suggestedModel": "haiku"
    },
    {
      "id": "US-002",
      "title": "Comment API Endpoints - Create and Read",
      "description": "As a user, I want to post comments on blog posts and view existing comments so that I can participate in discussions",
      "priority": 1,
      "acceptanceCriteria": [
        "Create POST /api/posts/:id/comments endpoint to submit new comments",
        "Create GET /api/posts/:id/comments endpoint to retrieve comments (with pagination)",
        "Validate comment content (max 2000 chars, required fields)",
        "Support parent_comment_id parameter for reply threading",
        "Return comments in chronological order with nested replies",
        "Write API integration tests"
      ],
      "passes": false,
      "notes": "",
      "fileScope": [
        "lib/api/routes/comments.py",
        "lib/api/schemas/comment.py",
        "tests/api/test_comments.py"
      ],
      "estimatedComplexity": "medium",
      "dependencies": ["US-001"],
      "suggestedModel": "sonnet"
    },
    {
      "id": "US-003",
      "title": "Comment Threading Logic",
      "description": "As a user, I want to reply to comments and see nested comment threads so that I can have focused discussions",
      "priority": 2,
      "acceptanceCriteria": [
        "Implement recursive comment tree builder (max 3 levels deep)",
        "Add validation to prevent circular parent references",
        "Create helper function to flatten thread for display",
        "Add comment depth field to API responses",
        "Handle edge cases (deleted parent comments, orphaned replies)",
        "Write unit tests for threading logic"
      ],
      "passes": false,
      "notes": "",
      "fileScope": [
        "lib/services/comment_threading.py",
        "tests/services/test_comment_threading.py"
      ],
      "estimatedComplexity": "medium",
      "dependencies": ["US-002"],
      "suggestedModel": "sonnet"
    },
    {
      "id": "US-004",
      "title": "Markdown Support in Comments",
      "description": "As a user, I want to use Markdown formatting in my comments so that I can emphasize points and add links",
      "priority": 2,
      "acceptanceCriteria": [
        "Integrate markdown parser (e.g., markdown-it or commonmark)",
        "Sanitize HTML output to prevent XSS attacks",
        "Add markdown-to-HTML conversion in API response",
        "Whitelist safe Markdown features (bold, italic, links, code blocks)",
        "Add preview mode to comment form on frontend",
        "Write security tests for XSS prevention"
      ],
      "passes": false,
      "notes": "",
      "fileScope": [
        "lib/services/markdown_processor.py",
        "frontend/src/components/CommentForm.tsx",
        "tests/services/test_markdown_processor.py"
      ],
      "estimatedComplexity": "simple",
      "dependencies": ["US-002"],
      "suggestedModel": "haiku"
    },
    {
      "id": "US-005",
      "title": "Comment Moderation Dashboard",
      "description": "As an admin, I want to review and moderate comments so that I can maintain comment quality and prevent spam",
      "priority": 1,
      "acceptanceCriteria": [
        "Create admin dashboard page at /admin/comments",
        "Display pending comments with approve/reject/delete/spam buttons",
        "Filter comments by status (pending, approved, rejected, spam)",
        "Bulk actions (approve all, delete selected)",
        "Show comment context (blog post title, parent comment if reply)",
        "Add pagination for large comment lists"
      ],
      "passes": false,
      "notes": "",
      "fileScope": [
        "lib/api/routes/admin/comments.py",
        "frontend/src/pages/admin/CommentModeration.tsx",
        "tests/api/test_admin_comments.py"
      ],
      "estimatedComplexity": "medium",
      "dependencies": ["US-003"],
      "suggestedModel": "sonnet"
    },
    {
      "id": "US-006",
      "title": "Email Notification System",
      "description": "As a commenter, I want to receive email notifications when someone replies to my comment so that I can stay engaged in discussions",
      "priority": 2,
      "acceptanceCriteria": [
        "Create email notification service",
        "Send email when reply is posted to user's comment (after moderation approval)",
        "Email includes: commenter name, reply excerpt, link to comment thread",
        "Use email template system for consistent formatting",
        "Add unsubscribe link to notification emails",
        "Write background job to send notifications asynchronously"
      ],
      "passes": false,
      "notes": "",
      "fileScope": [
        "lib/services/email_notifications.py",
        "lib/jobs/send_comment_notification.py",
        "templates/email/comment_reply.html",
        "tests/services/test_email_notifications.py"
      ],
      "estimatedComplexity": "medium",
      "dependencies": ["US-005"],
      "suggestedModel": "sonnet"
    },
    {
      "id": "US-007",
      "title": "Daily Digest for Blog Authors",
      "description": "As a blog author, I want to receive a daily digest of new comments on my posts so that I can stay informed without constant notifications",
      "priority": 3,
      "acceptanceCriteria": [
        "Create scheduled job to run daily at 9 AM",
        "Group comments by blog post for each author",
        "Include comment count, top commenters, flagged comments",
        "Only send if there are new comments since last digest",
        "Add user preference to enable/disable digests",
        "Write digest email template"
      ],
      "passes": false,
      "notes": "",
      "fileScope": [
        "lib/jobs/daily_comment_digest.py",
        "lib/services/digest_generator.py",
        "templates/email/comment_digest.html",
        "tests/jobs/test_daily_comment_digest.py"
      ],
      "estimatedComplexity": "simple",
      "dependencies": ["US-006"],
      "suggestedModel": "haiku"
    },
    {
      "id": "US-008",
      "title": "Frontend Comment Integration",
      "description": "As a blog reader, I want to see comments on blog posts and interact with them so that I can join the conversation",
      "priority": 1,
      "acceptanceCriteria": [
        "Add comment section component to blog post pages",
        "Display comments with threading (indented replies)",
        "Add comment form with Markdown preview",
        "Show comment count on blog post list",
        "Add loading states and error handling",
        "Write frontend integration tests"
      ],
      "passes": false,
      "notes": "",
      "fileScope": [
        "frontend/src/components/CommentSection.tsx",
        "frontend/src/components/CommentThread.tsx",
        "frontend/src/hooks/useComments.ts",
        "tests/frontend/CommentSection.test.tsx"
      ],
      "estimatedComplexity": "medium",
      "dependencies": ["US-004"],
      "suggestedModel": "sonnet"
    }
  ],
  "complexity": 3,
  "estimatedDuration": "2-3 weeks"
}
```

## Step 5: Understand the Generated PRD

Let's break down what Claude created:

### Project Metadata

```json
{
  "project": "blog-comment-system",
  "branchName": "feature/blog-comment-system",
  "description": "Implement a comment system...",
  "complexity": 3,
  "estimatedDuration": "2-3 weeks"
}
```

- **Project name:** Derived from your goal (kebab-case)
- **Branch name:** Git branch for this feature work
- **Complexity:** Level 3 (Complex) based on story count and scope
- **Duration:** Estimated from story complexity and count

### Story Structure

Each story follows the user story format:

```json
{
  "id": "US-002",
  "title": "Comment API Endpoints - Create and Read",
  "description": "As a user, I want to post comments...",
  "priority": 1,
  "acceptanceCriteria": [
    "Create POST /api/posts/:id/comments endpoint...",
    "Create GET /api/posts/:id/comments endpoint...",
    ...
  ],
  "fileScope": [
    "lib/api/routes/comments.py",
    "tests/api/test_comments.py"
  ],
  "estimatedComplexity": "medium",
  "dependencies": ["US-001"],
  "suggestedModel": "sonnet"
}
```

**Key Elements:**
- **Priority:** 1 = critical path, 2 = important, 3 = nice-to-have
- **Acceptance Criteria:** 3-5 specific, testable requirements
- **File Scope:** Predicted files based on codebase analysis
- **Complexity:** simple/medium/complex
- **Dependencies:** Stories that must complete first
- **Suggested Model:** haiku (simple), sonnet (medium), opus (complex)

### Dependency Graph

The generated dependencies create a logical execution order:

```
US-001 (Database Schema)
  ├─→ US-002 (API Endpoints)
  │     ├─→ US-003 (Threading Logic)
  │     │     └─→ US-005 (Moderation Dashboard)
  │     │           └─→ US-006 (Email Notifications)
  │     │                 └─→ US-007 (Daily Digest)
  │     └─→ US-004 (Markdown Support)
  │           └─→ US-008 (Frontend Integration)
```

## Step 6: Review and Refine

The generated PRD is a solid starting point, but you should review and adjust:

### Check 1: Story Granularity

**Question:** Are stories the right size?

**Too Large:**
```json
{
  "id": "US-002",
  "acceptanceCriteria": [
    "Create 5 API endpoints",
    "Add authentication",
    "Write 20 tests",
    "Deploy to production"
  ]
}
```

**Right Size:**
```json
{
  "id": "US-002",
  "acceptanceCriteria": [
    "Create POST endpoint for creating comments",
    "Create GET endpoint for retrieving comments",
    "Add pagination support",
    "Write integration tests for both endpoints"
  ]
}
```

### Check 2: File Scopes

**Question:** Are file scopes accurate for your codebase?

If your project structure differs, update file paths:

```bash
# Generated file scope (assumes Python)
"fileScope": ["lib/models/comment.py"]

# Your actual structure (Node.js/TypeScript)
"fileScope": ["src/models/Comment.ts"]
```

### Check 3: Dependencies

**Question:** Are dependencies correct?

Look for:
- Missing dependencies (Story B needs Story A but isn't listed)
- Unnecessary dependencies (Story B can run in parallel with Story A)
- Circular dependencies (Story A depends on B, B depends on A - invalid!)

### Check 4: Priorities

**Question:** Do priorities match your business needs?

Adjust priorities based on:
- User value (what delivers value fastest?)
- Technical constraints (what must be built first?)
- Risk mitigation (what's most uncertain?)

## Step 7: Save the Refined PRD

Save your reviewed PRD with a clear filename:

```bash
# Option 1: Accept default naming
# Saves to: prd-blog-comment-system.json

# Option 2: Custom output path
./claude-loop.sh --dynamic "Your goal" --dynamic-output prd-comments-v1.json

# Option 3: Generate to stdout, manually save
./claude-loop.sh --dynamic "Your goal" > prd-draft.json
# Review and edit
vim prd-draft.json
# Save as final
cp prd-draft.json prd-comments.json
```

## Step 8: Validate the PRD

Before executing, validate the PRD structure:

```bash
# Using prd-validator skill (Phase 2)
./claude-loop.sh --skill prd-validator prd-comments.json

# Using prd-parser
bash lib/prd-parser.sh validate prd-comments.json

# Check for circular dependencies
python3 lib/dependency-graph.py check-cycles prd-comments.json

# View execution plan
python3 lib/dependency-graph.py plan prd-comments.json
```

## Step 9: Execute the Generated PRD

Now execute your generated and refined PRD:

```bash
./claude-loop.sh prd-comments.json
```

With adaptive splitting enabled, you get the best of both worlds:
- **Generated plan:** Quick start from natural language goal
- **Adaptive execution:** Automatic adjustment if stories are more complex than estimated

## Advanced: Refining Generation Prompts

For better results, structure your goals like this:

### Template

```
[PROJECT NAME]

[OVERVIEW - 1-2 sentences]

[FEATURES - Bulleted list]
1. Feature Area:
   - Specific requirement
   - Specific requirement

2. Feature Area:
   - Specific requirement
   - Specific requirement

[TECHNICAL CONSTRAINTS - If any]
- Database: [specify]
- Authentication: [specify]
- API style: [REST/GraphQL/etc]
- Framework: [specify if relevant]

[NON-FUNCTIONAL REQUIREMENTS - If any]
- Performance: [specify]
- Security: [specify]
- Scalability: [specify]
```

### Example: E-Commerce Checkout

```
E-Commerce Checkout System

Build a complete checkout flow for the e-commerce platform.

Features:
1. Shopping Cart:
   - Add/remove items
   - Update quantities
   - Calculate totals with tax

2. Checkout Process:
   - Multi-step checkout (cart → shipping → payment → confirmation)
   - Guest checkout option
   - Save address for logged-in users

3. Payment Integration:
   - Integrate Stripe payment gateway
   - Support credit cards and digital wallets
   - Handle payment errors and retries

4. Order Management:
   - Create order record on successful payment
   - Send order confirmation email
   - Update inventory after purchase

Technical Constraints:
- Database: PostgreSQL
- Authentication: Use existing JWT system
- API: RESTful endpoints
- Payment: Stripe API v2023-10-16

Non-Functional Requirements:
- Performance: Checkout must complete in <3 seconds
- Security: PCI compliance for payment data
- Reliability: Idempotent payment processing
```

## Common Pitfalls and Solutions

### Pitfall 1: Vague Goals

**Problem:**
```
./claude-loop.sh --dynamic "Add authentication"
```

**Too vague!** Claude doesn't know:
- What kind of authentication? (Password, OAuth, SSO, etc.)
- What features? (Login, signup, password reset, 2FA, etc.)
- Technical constraints? (Database, framework, etc.)

**Solution:**
```
./claude-loop.sh --dynamic "Implement JWT-based authentication with:
- Email/password login
- User registration with email verification
- Password reset via email
- Session management with refresh tokens
- Use PostgreSQL for user storage"
```

### Pitfall 2: Over-Specifying Implementation

**Problem:**
```
./claude-loop.sh --dynamic "Create a LoginController class with authenticateUser method that calls UserRepository.findByEmail and checks password with bcrypt.compare then generates JWT with jsonwebtoken.sign..."
```

**Too detailed!** This is implementation code, not a goal.

**Solution:**
```
./claude-loop.sh --dynamic "Implement user login functionality with email/password authentication and JWT token generation"
```

Let Claude decompose into implementation steps.

### Pitfall 3: Ignoring Codebase Structure

**Problem:** Generated file scopes don't match your project.

**Solution:**
```bash
# Enable codebase analysis
./claude-loop.sh --dynamic "Your goal" --codebase-analysis

# Or manually refine after generation
vim prd-generated.json  # Update file scopes
```

### Pitfall 4: Not Reviewing Before Execution

**Problem:** Executing generated PRD immediately without review.

**Solution:** Always review:
1. Generate to file
2. Review stories, dependencies, file scopes
3. Validate PRD structure
4. Then execute

## Iteration Workflow

Dynamic generation shines when you iterate:

```bash
# Iteration 1: Generate initial PRD
./claude-loop.sh --dynamic "Your goal" --dynamic-output draft-v1.json

# Review, identify issues

# Iteration 2: Refine goal, regenerate
./claude-loop.sh --dynamic "Refined goal with more details" --dynamic-output draft-v2.json

# Review again

# Iteration 3: Manual edits
cp draft-v2.json prd-final.json
vim prd-final.json  # Fine-tune

# Execute
./claude-loop.sh prd-final.json
```

## Key Takeaways

1. **Be specific but not prescriptive** - Describe what, not how
2. **Structure your goals** - Use bullets, sections, technical constraints
3. **Enable codebase analysis** - Better file scope predictions
4. **Always review** - Generated PRDs are starting points, not final drafts
5. **Iterate** - Refine your goal and regenerate if needed
6. **Validate before executing** - Check dependencies, file scopes, story size

## Next Steps

- **Try it:** Generate a PRD for your next project
- **Experiment:** Try different goal formats and see what works best
- **Share:** Document your goal templates for your team
- **Combine:** Use with adaptive splitting for fully adaptive workflows

## Related Documentation

- [Getting Started with Phase 3](./getting-started.md)
- [Adaptive Splitting Tutorial](./tutorial-adaptive-splitting.md)
- [PRD Structure Reference](../reference/prd-schema.md)
- [Troubleshooting Guide](../troubleshooting/phase3-issues.md)

---

**Tutorial Complete!** You can now generate PRDs from natural language goals. Try it on your next feature!

# Phase 2 Demo Video Storyboard

10-minute demo video showcasing claude-loop Phase 2 features.

## Video Metadata

- **Duration**: 10 minutes
- **Target Audience**: Developers familiar with AI coding tools
- **Goal**: Show Phase 2 features in action, convert viewers to users
- **Format**: Screen recording with voiceover
- **Platform**: YouTube, Twitter, GitHub

---

## Structure Overview

```
[0:00-1:00] Introduction & Problem Statement
[1:00-2:30] Scene 1: Skills Framework
[2:30-4:30] Scene 2: Quick Task Mode
[4:30-6:00] Scene 3: Daemon Mode
[6:00-8:00] Scene 4: Visual Dashboard
[8:00-9:00] Scene 5: Notifications
[9:00-10:00] Conclusion & Call to Action
```

---

## Scene-by-Scene Breakdown

### Opening [0:00-1:00]

**Visual**: Claude Loop logo animation, then terminal window

**Voiceover**:
> "claude-loop revolutionized autonomous development by turning PRDs into working features. But we heard your feedback: 'I love it for complex features, but it feels like overkill for quick fixes.' Today, we're introducing Phase 2—five new capabilities that make claude-loop 10x faster, 40-70% cheaper, and way more user-friendly."

**On-Screen Text**:
```
claude-loop Phase 2
• Skills: Zero-cost operations
• Quick Tasks: Natural language
• Daemon: Background execution
• Dashboard: Real-time monitoring
• Notifications: Async awareness
```

**Technical Setup**:
- Clean terminal with custom prompt
- Project: Simple Express.js API
- Directory: `~/demo/express-api`

---

### Scene 1: Skills Framework [1:00-2:30]

**Hook**: "Let's start with something that'll save you hundreds of dollars a month."

#### Part 1: The Problem [1:00-1:20]

**Visual**: Split screen - Before vs After

**Left Side (Phase 1)**:
```bash
# Validate PRD manually
cat prd.json  # Show JSON on screen
# Copy-paste into Claude chat
# Wait for response
# Time: 30 seconds
# Cost: $0.15
```

**Right Side (Phase 2)**:
```bash
./claude-loop.sh --skill prd-validator --skill-arg prd.json

Output:
✓ JSON syntax valid
✓ All required fields present
✓ No circular dependencies
✓ PRD is valid

# Time: <1 second
# Cost: $0.00
```

**Voiceover**:
> "Skills are deterministic operations that run instantly at zero cost. Instead of paying Claude to validate JSON, we use a Python script."

#### Part 2: Skills in Action [1:20-2:00]

**Visual**: Terminal, list skills

```bash
./claude-loop.sh --list-skills
```

**On-Screen**: Show skill list with descriptions scrolling

**Voiceover**:
> "Phase 2 includes five built-in skills: PRD validator, test scaffolder, commit formatter, API spec generator, and cost optimizer. Each one replaces an LLM call with a zero-cost script."

#### Part 3: Custom Skills [2:00-2:30]

**Visual**: Quick custom skill creation

```bash
# Create skill
mkdir -p skills/hello-world/scripts

cat > skills/hello-world/SKILL.md << 'EOF'
# /hello-world - Demo Skill
A simple demo skill
EOF

cat > skills/hello-world/scripts/main.sh << 'EOF'
#!/bin/bash
echo "Hello from custom skill!"
EOF

chmod +x skills/hello-world/scripts/main.sh

# Use it
./claude-loop.sh --skill hello-world
```

**Voiceover**:
> "Creating custom skills is trivial. Just add a markdown file and optionally a script. Skills load metadata at startup, instructions on-demand, and scripts never touch the LLM context. That's 50-100x cost reduction for deterministic operations."

**On-Screen Text**: "50-100x cost reduction"

---

### Scene 2: Quick Task Mode [2:30-4:30]

**Hook**: "Now let's fix a bug. Watch how fast this is."

#### Part 1: The Old Way [2:30-3:00]

**Visual**: Fast-forward montage

```bash
# Create PRD (show JSON file)
nano bug-fix.json
# ... typing JSON ...

# Execute
./claude-loop.sh --prd bug-fix.json
# ... waiting ...

# Time: 15-20 minutes
```

**Voiceover**:
> "In Phase 1, even a one-line fix required creating a PRD JSON file. It works, but feels heavy."

#### Part 2: Quick Mode Demo [3:00-4:00]

**Visual**: Real-time execution

```bash
./claude-loop.sh quick "fix the email validation in auth.js" --dry-run
```

**On-Screen**: Show generated plan
```
Quick Task Execution Plan:
1. Read current auth.js implementation
2. Identify email validation logic
3. Implement regex-based validation
4. Add error messages
5. Verify changes
Complexity: medium (35/100)
Estimated cost: $0.32
```

**Voiceover**:
> "Quick mode is just natural language. Describe your task, Claude generates a plan, you approve, and it executes. The dry-run flag shows you the plan without executing."

**Visual**: Now run without dry-run

```bash
./claude-loop.sh quick "fix the email validation in auth.js" --commit
```

**On-Screen**: Fast-forward showing:
- Plan approval
- Execution progress
- Success message
- Auto-commit

**Voiceover**:
> "With the commit flag, changes are automatically committed with a proper Conventional Commits message. What took 20 minutes now takes 2."

**On-Screen Text**: "10x faster for simple tasks"

#### Part 3: Complexity Detection [4:00-4:30]

**Visual**: Show complex task

```bash
./claude-loop.sh quick "rewrite the entire authentication system with OAuth, add tests, update docs" --escalate
```

**On-Screen**: Show warning
```
⚠️  COMPLEXITY WARNING ⚠️
This task appears complex (score: 85/100)
Consider using PRD mode instead
Continue? [y/N]
```

**Voiceover**:
> "Quick mode isn't for everything. Complexity detection automatically identifies tasks that need a full PRD. The escalate flag offers to convert to PRD mode if needed."

---

### Scene 3: Daemon Mode [4:30-6:00]

**Hook**: "What if you could submit work and go to sleep?"

#### Part 1: The Problem [4:30-5:00]

**Visual**: Sad developer at computer late at night

**On-Screen Scenario**:
```
10:00 PM: Start feature-1.json (30 min)
10:30 PM: Completes, start feature-2.json (30 min)
11:00 PM: Completes, start feature-3.json (30 min)
11:30 PM: Finally done!

Problem: Manual babysitting for 1.5 hours
```

**Voiceover**:
> "Phase 1 was sequential. You could only run one PRD at a time, and you had to stay awake to kick off the next one."

#### Part 2: Daemon Solution [5:00-5:40]

**Visual**: Terminal, daemon workflow

```bash
# Start daemon
./claude-loop.sh daemon start

Output:
Daemon started (PID: 12345)
Workers: 1
Queue: .claude-loop/daemon/queue.json
```

```bash
# Submit all three features
./claude-loop.sh daemon submit feature-1.json --notify email
./claude-loop.sh daemon submit feature-2.json --notify email
./claude-loop.sh daemon submit feature-3.json --notify email

Output:
Task abc123 submitted (priority: normal)
Task def456 submitted (priority: normal)
Task ghi789 submitted (priority: normal)
```

**Voiceover**:
> "Daemon mode is fire-and-forget. Start the daemon, submit your PRDs, and walk away. The daemon processes them in the background and sends you an email when each one completes."

#### Part 3: Queue Management [5:40-6:00]

**Visual**: Monitor queue

```bash
./claude-loop.sh daemon queue
```

**On-Screen**: Show queue with visual icons

**Voiceover**:
> "Check the queue anytime to see what's running, pending, or completed. You can even pause the queue, cancel tasks, or submit high-priority urgent fixes that jump to the front."

**On-Screen Text**: "Fire-and-forget workflow"

---

### Scene 4: Visual Dashboard [6:00-8:00]

**Hook**: "But the real magic happens in the browser."

#### Part 1: Launch Dashboard [6:00-6:20]

**Visual**: Terminal + browser

```bash
./claude-loop.sh dashboard start

Output:
Dashboard started on http://localhost:8080
Auth token: AbCdEf123456
```

**Visual**: Browser opens, shows login prompt

**On-Screen**: Enter token, dashboard loads with smooth animation

**Voiceover**:
> "The visual dashboard gives you real-time visibility into every execution. No more tailing log files."

#### Part 2: Start Execution [6:20-6:40]

**Visual**: Terminal

```bash
./claude-loop.sh --prd large-feature.json
```

**Visual**: Switch to browser showing execution starting

**Voiceover**:
> "As soon as you start a PRD, the dashboard updates automatically via Server-Sent Events."

#### Part 3: UI Tour [6:40-7:40]

**Visual**: Smooth tour of dashboard UI

**Section 1: Story Grid [6:40-6:55]**

**On-Screen**: Highlight story cards

```
Story Status Grid:
┌─ US-001 ──────┐  ┌─ US-002 ──────┐  ┌─ US-003 ──────┐
│ Auth System   │  │ User Profile  │  │ Dashboard     │
│ ✓ Complete    │  │ 🔄 In Progress│  │ ⏳ Pending    │
└───────────────┘  └───────────────┘  └───────────────┘
```

**Voiceover**:
> "The story grid shows all your user stories color-coded by status. Green means complete, yellow with a pulsing animation means in progress, and gray means pending."

**Section 2: Live Execution [6:55-7:10]**

**On-Screen**: Highlight live section

```
Current Story: US-002: User Profile
Progress: [████████░░] 75%
Elapsed: 12m 34s
Running Cost: $1.23
```

**Voiceover**:
> "The live execution section shows current progress, elapsed time, and running cost. All updating in real-time."

**Section 3: Logs Tab [7:10-7:25]**

**On-Screen**: Click logs tab, show streaming logs

```
[00:12:34] Starting execution
[00:12:35] ✓ Story US-001 complete
[00:12:36] Running tests...
[00:12:37] ⚠️ Test coverage below 80%
```

**Voiceover**:
> "The logs tab streams color-coded logs in real-time. Info, success, warning, and error messages are all color-coded for easy scanning."

**Section 4: Cost Tracker [7:25-7:40]**

**On-Screen**: Click cost tracker tab

```
Total Cost: $1.23
Input Tokens: 45,000
Output Tokens: 12,000
Budget Remaining: $8.77

⚠️ Budget alert when limit exceeded
```

**Voiceover**:
> "Cost tracker shows token usage and total spend. Set a budget limit and get alerted if you exceed it. Perfect for keeping projects on budget."

#### Part 4: Mobile Demo [7:40-8:00]

**Visual**: iPhone screen recording

**On-Screen**: Same dashboard on mobile, works perfectly

**Voiceover**:
> "The dashboard is fully responsive. Check progress from your phone while grabbing coffee."

**On-Screen Text**: "Real-time visibility, anywhere"

---

### Scene 5: Notifications [8:00-9:00]

**Hook**: "How do you know when background work completes?"

#### Part 1: Setup [8:00-8:20]

**Visual**: Terminal, config file

```bash
# Initialize notifications
./lib/notifications.sh init

# Configure (edit file)
nano .claude-loop/daemon/notifications.json
```

**On-Screen**: Show JSON config with highlighted sections

```json
{
  "email": {
    "enabled": true,
    "to": ["you@example.com"]
  },
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/..."
  }
}
```

**Voiceover**:
> "Notifications work with email, Slack, or generic webhooks. Configure once, use everywhere."

#### Part 2: Demo [8:20-8:50]

**Visual**: Terminal submitting task

```bash
./claude-loop.sh daemon submit overnight-work.json --notify email,slack
```

**Visual**: Split screen - time-lapse showing:
- Left: Terminal showing task processing
- Right: Inbox and Slack showing notifications arriving

**On-Screen**: Show notification content

**Email**:
```
Subject: claude-loop: Task abc123 completed

✅ Task Completed Successfully

Project: Express API
Stories: 5/5 completed
Time: 45 minutes
Cost: $3.21

All user stories implemented successfully.
```

**Slack**:
```
[Green notification]
claude-loop: Task abc123 completed
Project: Express API | Stories: 5/5 | Time: 45m | Cost: $3.21
```

**Voiceover**:
> "When the task completes, you get notified via all configured channels. Submit work before bed, wake up to completion notifications."

#### Part 3: Custom Templates [8:50-9:00]

**Visual**: Show template file

```bash
cat templates/notifications/success.txt
```

**On-Screen**: Show template with variables

**Voiceover**:
> "Notification templates are fully customizable. Add your own variables, branding, or call-to-actions."

---

### Conclusion [9:00-10:00]

#### Part 1: Benefits Recap [9:00-9:30]

**Visual**: Split screen showing before/after

**On-Screen Comparison Table**:

```
Phase 1 vs Phase 2:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Task           Phase 1      Phase 2      Improvement
─────────────────────────────────────────────────────
Bug Fix        20 min       2 min        10x faster
Validation     $0.15        $0.00        100% cheaper
Overnight      Manual       Daemon       Automatic
Monitoring     Logs         Dashboard    Visual
Awareness      Terminal     Notify       Async
Monthly Cost   $160         $52          67% reduction
```

**Voiceover**:
> "Phase 2 makes claude-loop 10x faster for simple tasks, 40-70% cheaper overall, and way more user-friendly. All while maintaining full backward compatibility with Phase 1."

#### Part 2: Getting Started [9:30-9:50]

**Visual**: Terminal, quick commands

```bash
# Update to Phase 2
git pull origin main

# Try quick mode
./claude-loop.sh quick "your first task" --dry-run

# Start dashboard
./claude-loop.sh dashboard start

# Read docs
open docs/phase2/README.md
```

**On-Screen Text**:
```
Get Started:
1. Update: git pull origin main
2. Try: ./claude-loop.sh quick --help
3. Learn: docs/phase2/README.md
```

**Voiceover**:
> "Getting started is simple. Update to the latest version, try quick mode, and check out the documentation. Phase 2 is fully compatible with Phase 1, so there's zero risk."

#### Part 3: Call to Action [9:50-10:00]

**Visual**: End screen with links

**On-Screen**:
```
claude-loop Phase 2

📚 Documentation: github.com/your-repo/claude-loop/docs
💬 Discord: discord.gg/claude-loop
🐦 Twitter: @claude_loop
⭐ Star on GitHub: github.com/your-repo/claude-loop

Welcome to the Future of Autonomous Development
```

**Voiceover**:
> "Try Phase 2 today and experience the future of autonomous development. Links in the description. Thanks for watching!"

---

## Production Notes

### Equipment

- **Screen Recording**: OBS Studio or ScreenFlow
- **Microphone**: Blue Yeti or similar (clear audio essential)
- **Editing**: Final Cut Pro or Adobe Premiere

### Visual Guidelines

**Terminal**:
- Use Warp or iTerm2 with custom theme
- Font: Fira Code or Menlo, 16-18pt
- Color scheme: Dracula or Solarized Dark
- Clear bash prompt: `username@machine:~/path $`

**Browser**:
- Chrome with no extensions showing
- Clean bookmark bar
- Dashboard in dark mode
- Window size: 1280x720

**On-Screen Text**:
- Font: Helvetica Neue Bold
- Size: 48pt for main text, 36pt for details
- Color: White with subtle drop shadow
- Duration: 3-5 seconds per card
- Animation: Fade in, hold, fade out

### Audio Guidelines

**Voiceover**:
- Pace: 150-160 words per minute (conversational)
- Tone: Enthusiastic but professional
- Volume: Consistent, normalized
- Background: Silent or very subtle ambient

**Music** (optional):
- Upbeat electronic/tech background
- Volume: -20dB (subtle, not distracting)
- Intro: 0:00-0:15
- Outro: 9:45-10:00

### Editing Guidelines

**Cuts**:
- Remove dead air (pause > 2 seconds)
- Speed up wait times (execution, page loads)
- Keep real-time for key demonstrations

**B-Roll**:
- Quick cuts between terminal and browser
- Zoom in on important sections
- Highlight text with subtle box outlines

**Transitions**:
- Fast cuts (no fades)
- Exception: Scene transitions can have 0.5s fade

---

## Script Timing Breakdown

| Scene | Duration | Words | Recording Time |
|-------|----------|-------|----------------|
| Opening | 1:00 | 160 | 5 min |
| Scene 1 | 1:30 | 240 | 10 min |
| Scene 2 | 2:00 | 320 | 15 min |
| Scene 3 | 1:30 | 240 | 10 min |
| Scene 4 | 2:00 | 320 | 15 min |
| Scene 5 | 1:00 | 160 | 10 min |
| Conclusion | 1:00 | 160 | 5 min |
| **Total** | **10:00** | **1,600** | **70 min** |

**Production Estimate**:
- Recording: 70 minutes
- Editing: 3-4 hours
- Review & revisions: 1-2 hours
- **Total**: 5-6 hours

---

## Distribution Plan

### YouTube

- **Title**: "claude-loop Phase 2: 10x Faster AI Development with Skills, Quick Tasks & Visual Dashboard"
- **Description**: Include links, timestamps, installation instructions
- **Tags**: AI coding, autonomous development, Claude AI, developer tools, automation
- **Thumbnail**: Split screen showing terminal (left) and dashboard (right)
- **Playlist**: Add to "claude-loop Tutorials"

**Timestamps** (in description):
```
0:00 Introduction
1:00 Skills Framework (Zero-Cost Operations)
2:30 Quick Task Mode (Natural Language)
4:30 Daemon Mode (Background Execution)
6:00 Visual Dashboard (Real-Time Monitoring)
8:00 Notifications (Async Awareness)
9:00 Getting Started
```

### Social Media

**Twitter Thread**:
```
🚀 claude-loop Phase 2 is here!

5 game-changing features:
• Skills: Zero-cost operations
• Quick Tasks: Natural language
• Daemon: Background execution
• Dashboard: Real-time monitoring
• Notifications: Async awareness

10-min demo 👇
[video link]

[1/8]
```

**Reddit** (r/programming, r/devops, r/artificial):
- Title: "claude-loop Phase 2: 10x Faster Autonomous Development"
- Post type: Video + text
- Include: Problem statement, feature overview, demo link

**Hacker News**:
- Title: "claude-loop Phase 2: Skills, Quick Tasks, and Visual Dashboard"
- Post link to GitHub repo and video
- Engage with comments

---

## Success Metrics

**Video Performance**:
- Target views: 10,000 in first week
- Watch time: >60% average (>6 minutes)
- Engagement: >5% like rate
- Comments: >100 in first week

**Conversion**:
- GitHub stars: +500
- Installs: +1,000
- Discord joins: +200
- Documentation page views: +5,000

**Feedback**:
- Survey after watching
- Track feature adoption (analytics)
- Monitor GitHub issues/discussions

---

## Assets Checklist

Pre-production:
- [ ] Demo project setup (Express.js API)
- [ ] Sample PRD files created
- [ ] Dashboard configured and styled
- [ ] Notification channels tested
- [ ] Custom skills created for demo

Recording:
- [ ] Terminal screen recording (all scenes)
- [ ] Browser screen recording (dashboard)
- [ ] Mobile screen recording (responsive demo)
- [ ] Voiceover audio (separate track)

Post-production:
- [ ] Video edited and rendered
- [ ] Thumbnail created (1280x720)
- [ ] Description written with timestamps
- [ ] Captions/subtitles added
- [ ] Music licensed (if used)

Distribution:
- [ ] YouTube upload
- [ ] Twitter thread
- [ ] Reddit posts
- [ ] Hacker News submission
- [ ] Discord announcement
- [ ] GitHub README update with video embed

---

## Contingency Plans

**If Recording Fails**:
- Use terminal recording software (asciinema) as backup
- Can convert to animated GIFs for social

**If Demo Breaks**:
- Have pre-recorded segments ready
- Edit together seamlessly
- Voiceover can cover technical issues

**If Timing Runs Long**:
- Cut Scene 5 to brief mention
- Focus on Skills, Quick Mode, Dashboard (core features)
- Link to full tutorial for Notifications

**If Timing Runs Short**:
- Add more detailed examples in Scene 2 and 4
- Show additional skills
- Extended dashboard tour

---

## Post-Launch

**Week 1**:
- Monitor comments and respond
- Share clips on Twitter (30-60s highlights)
- Create follow-up content based on questions

**Week 2-4**:
- Create tutorial series (one per feature)
- User showcase videos (if users submit)
- Case study interviews with beta testers

**Ongoing**:
- Update video description with new features
- Pin top comment with latest updates
- Add to documentation as embedded video

---

## See Also

- [Announcement Blog Post](announcement-blog-post.md)
- [Phase 2 Documentation](README.md)
- [Before/After Comparison](before-after-comparison.md)
- [Tutorial Series](../tutorials/)

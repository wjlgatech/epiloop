# Phase 1 Demo Video Script

**Duration**: 3-4 minutes
**Target Audience**: Developers familiar with AI coding tools
**Goal**: Show Phase 1 features solving real problems

---

## Scene 1: The Problem (0:00 - 0:30)

### Visual
- Split screen: Two developers at their computers
- Developer A (left): Pre-Phase 1 experience, looks frustrated
- Developer B (right): Phase 1 experience, looks calm

### Voiceover
> "Meet two developers using claude-loop to build the same feature..."

### On-screen text
```
Developer A: Pre-Phase 1
- No visibility
- Manual PRD writing
- Hoping for the best

Developer B: Phase 1
- Real-time progress
- Template-based PRD
- Safe & controlled
```

### Developer A (frustrated)
```bash
# Terminal shows:
$ ./claude-loop.sh
# ...nothing happens for 30 seconds
# Developer checks logs repeatedly
$ tail -f .claude-loop/logs/iteration.log
```

### Developer B (calm)
```bash
# Terminal shows rich progress UI:
╔════════════════════════════════════════════════════════════════╗
║ Story 2/7: Implement POST /api/tasks
║ Overall Progress: [███░░░░░░░] 2/7 (29%)
║ Time: 5m elapsed | ~12m remaining
║ Currently: Writing tests
║   ✅ Create endpoint handler
║   ⏳ Add input validation
║   ○ Write integration tests
╚════════════════════════════════════════════════════════════════╝
```

---

## Scene 2: Feature 1 - PRD Templates (0:30 - 1:10)

### Visual
- Close-up of Developer B's terminal
- Show template selection and generation

### Voiceover
> "Developer B starts with a template - no more writing PRDs from scratch."

### Developer B types
```bash
$ ./claude-loop.sh --list-templates
```

### Screen shows
```
Available PRD Templates:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 web-feature       - Full-stack feature with frontend + backend
🔌 api-endpoint      - REST/GraphQL API endpoint
🔧 refactoring       - Code restructuring
🐛 bug-fix           - Issue reproduction and fix
📚 documentation     - README/docs updates
🧪 testing           - Test coverage expansion
```

### Developer B continues
```bash
$ ./claude-loop.sh --template api-endpoint \
  --template-var ENDPOINT_NAME=TaskManager \
  --template-var DESCRIPTION="CRUD API for managing tasks"
```

### Screen shows
```
✅ PRD generated: prd.json
   - 7 user stories
   - 28 acceptance criteria
   - Model, endpoints, validation, tests, docs

Ready to run in 30 seconds!
```

### On-screen comparison
```
Developer A: 30 minutes writing PRD ⏱️
Developer B: 30 seconds with template ⚡
```

---

## Scene 3: Feature 2 - Real-Time Progress (1:10 - 1:50)

### Visual
- Split screen again
- Developer A: checking logs, looking confused
- Developer B: watching progress UI, working on other things

### Voiceover
> "While Developer A checks logs constantly, Developer B sees real-time progress."

### Developer A (confused)
```bash
# Terminal shows:
$ ./claude-loop.sh
# ...waiting...

# Checks logs:
$ tail -f .claude-loop/logs/iteration.log
[2026-01-13 11:00:00] Starting iteration 1
[2026-01-13 11:02:15] Claude Code running...
# ...still waiting, no progress indication
```

### Developer B (productive)
```bash
# Terminal shows live progress UI:
╔════════════════════════════════════════════════════════════════╗
║ Story 4/7: Add Input Validation and Error Handling
║
║ Overall Progress: [█████░░░░░] 4/7 (57%)
║ Time: 11m elapsed | ~8m remaining
║ Currently: Running integration tests
║
║ Acceptance Criteria:
║   ✅ Add Pydantic validation for request body
║   ✅ Add error handling for 400/404/500 responses
║   ✅ Write unit tests for validation logic
║   ⏳ Write integration tests for error cases
║   ○ Update API documentation with error responses
╚════════════════════════════════════════════════════════════════╝
```

### On-screen text
> "Developer B switches to email, checks back 5 minutes later, progress updated!"

---

## Scene 4: Feature 3 - Workspace Sandboxing (1:50 - 2:20)

### Visual
- Code editor showing file tree
- Highlight folders being modified

### Voiceover
> "Developer B uses workspace sandboxing to control exactly what gets changed."

### Developer B types
```bash
$ ./claude-loop.sh --workspace "src/api,tests/api"
```

### Screen shows
```
🔒 Workspace sandboxing enabled
   - Only src/api/ and tests/api/ can be modified
   - All other folders are protected

Starting execution...
```

### Visual: File tree animation
- `src/api/` - highlighted green (allowed)
- `tests/api/` - highlighted green (allowed)
- `config/` - greyed out (protected)
- `src/frontend/` - greyed out (protected)
- `.env` - greyed out (protected)

### Screen shows during execution
```
✅ Created: src/api/models/task.py
✅ Created: src/api/routes/tasks.py
✅ Created: tests/api/test_task_model.py
✅ Created: tests/api/test_task_endpoints.py

✅ Workspace validation: PASSED
   All changes within allowed folders!
```

### On-screen comparison
```
Without sandboxing: Changes anywhere ⚠️
With sandboxing: Controlled scope ✅
```

---

## Scene 5: Feature 4 - Safety Checkpoints (2:20 - 3:00)

### Visual
- Terminal showing checkpoint confirmation
- Developer making a decision

### Voiceover
> "When claude-loop needs to do something destructive, Developer B reviews and approves."

### Developer B's terminal shows
```bash
$ ./claude-loop.sh --safety-level cautious
```

### During execution, checkpoint appears
```
⚠️  CHECKPOINT CONFIRMATION REQUIRED ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Action: Create new directory
Path: src/api/models/

Reason: Organizing Task model in dedicated models directory
Impact: Low - organizational change only

Do you approve this action?
  [y] Yes     [n] No     [a] Yes to all     [q] Abort

Your choice: _
```

### Developer B types: `y`

### Later, more critical checkpoint
```
⚠️  CHECKPOINT CONFIRMATION REQUIRED ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Action: Delete 5 files
Files affected:
  - src/api/old_routes.py
  - src/api/deprecated.py
  - tests/api/old_tests.py
  - docs/old_api_spec.md
  - src/api/__init__.backup.py

Reason: Removing deprecated API code after refactoring
Impact: High - files will be permanently deleted

Do you approve this action?
  [y] Yes     [n] No     [a] Yes to all     [q] Abort

Your choice: _
```

### Developer B reviews files, types: `y`

### On-screen text
```
✅ Audit trail saved to .claude-loop/safety-log.jsonl
   All decisions recorded for review
```

---

## Scene 6: Results (3:00 - 3:30)

### Visual
- Split screen showing final results

### Developer A (frustrated)
```bash
# Terminal shows:
$ git status
# 47 files changed, 2150 insertions(+), 89 deletions(-)

# Files modified:
#   src/api/...
#   config/database.yaml (unexpected!)
#   .github/workflows/ci.yml (unexpected!)
#   src/frontend/App.tsx (unexpected!)

# Developer discovers unwanted changes
$ git diff config/database.yaml
# "Wait, why was this changed?!"
```

### Developer B (satisfied)
```bash
# Terminal shows:
╔════════════════════════════════════════════════════════════════╗
║ ✅ ALL STORIES COMPLETE!
║
║ Overall Progress: [██████████] 7/7 (100%)
║ Time: 14m 32s total
║
║ Summary:
║   - 7 stories completed
║   - 15 files created (all within src/api, tests/api)
║   - 28 acceptance criteria met ✅
║   - All tests passing ✅
║   - 4 checkpoints approved
╚════════════════════════════════════════════════════════════════╝

$ git status
# 15 files changed, 892 insertions(+)
# All changes within workspace boundaries ✅
```

### On-screen comparison
```
Developer A:                    Developer B:
━━━━━━━━━━━━━━━━━━━━━━━━━      ━━━━━━━━━━━━━━━━━━━━━━━━━
⏱️  45 minutes                   ⏱️  15 minutes
❓ Zero visibility               ✅ Full visibility
⚠️  Unwanted changes             ✅ Controlled changes
❌ Need to revert                ✅ Ready to commit
😰 High stress                   😌 Low stress
```

---

## Scene 7: Call to Action (3:30 - 4:00)

### Visual
- claude-loop logo and Phase 1 features summary

### Voiceover
> "Phase 1 transforms claude-loop from a black box to a transparent, safe, and fast development tool."

### On-screen text
```
🚀 Phase 1 Features

✅ Real-time progress indicators
✅ PRD templates (6 built-in)
✅ Workspace sandboxing
✅ Safety checkpoints

60x faster PRD creation
100% visibility
90% stress reduction
```

### Voiceover continues
> "Get started with Phase 1 today. It's 100% backwards compatible."

### On-screen text
```
📚 Learn more:
   docs/phase1/getting-started.md
   docs/phase1/tutorial.md

🔗 GitHub: github.com/your-org/claude-loop
```

### Final screen
```
claude-loop Phase 1
"Describe the feature. Go to lunch. Come back to a PR."

Now with 100% visibility 👀
```

---

## Camera Angles & Production Notes

### Setup
- **Camera 1**: Close-up of Developer A's screen (pre-Phase1)
- **Camera 2**: Close-up of Developer B's screen (Phase 1)
- **Camera 3**: Wide shot showing both developers side-by-side
- **Screencasts**: Pre-recorded terminal sessions (with real execution)

### Timing Guidelines
- Scene 1 (Problem): 30 seconds - Establish the pain
- Scene 2 (Templates): 40 seconds - Show speed improvement
- Scene 3 (Progress): 40 seconds - Show visibility improvement
- Scene 4 (Sandboxing): 30 seconds - Show control
- Scene 5 (Safety): 40 seconds - Show confidence
- Scene 6 (Results): 30 seconds - Compare outcomes
- Scene 7 (CTA): 30 seconds - Drive action

### Key Visual Elements
1. **Progress UI**: Use actual running claude-loop (not faked)
2. **Split screen**: Show contrast between experiences
3. **On-screen text**: Reinforce key metrics (60x, 100%, 90%)
4. **Smooth transitions**: Fade between scenes
5. **Background music**: Upbeat but not distracting

### Voice Talent
- **Voiceover artist**: Clear, enthusiastic, technical but accessible
- **Tone**: Helpful, not condescending
- **Pace**: Medium - clear enough to follow, fast enough to be engaging

### Alternative: Silent Video with Captions
If voiceover isn't available:
- Add on-screen captions for all narration
- Use larger text overlays for key points
- Extend scene durations by 10-20% for reading time
- Add background music throughout

---

## B-Roll Footage Needs

1. Terminal sessions running claude-loop (both versions)
2. Code editor showing generated files
3. Git diffs highlighting changes
4. Developer reactions (thinking, relieved, frustrated, satisfied)
5. Clock/time-lapse showing time differences
6. File tree animations showing workspace boundaries

---

## Distribution Platforms

- **YouTube**: Primary platform (4K, full resolution)
- **Twitter/X**: 30-second cut showing before/after split
- **LinkedIn**: 60-second version highlighting productivity gains
- **README.md**: Embedded YouTube link
- **Documentation**: Link from getting-started.md

---

## Accessibility Considerations

- **Captions**: Full captions for all spoken content
- **Alt text**: Describe visual comparisons for screen readers
- **Transcripts**: Full text transcript in docs/phase1/demo-video-transcript.txt
- **Color**: Don't rely only on red/green (use symbols too: ✅❌)

---

## Post-Production Checklist

- [ ] Color correction (match terminal colors)
- [ ] Audio levels normalized
- [ ] Captions added and synced
- [ ] Opening/closing titles
- [ ] Music volume balanced with voiceover
- [ ] Final export in multiple resolutions (4K, 1080p, 720p)
- [ ] Thumbnail image created (split screen comparison)
- [ ] Upload to YouTube with detailed description
- [ ] Add to playlist: "claude-loop Tutorials"

---

**Ready to film?** Use this script as a guide. Feel free to adapt based on your production capabilities and audience!

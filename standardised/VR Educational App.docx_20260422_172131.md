# VR EduSpace — Immersive Learning Platform

## Game Overview
VR EduSpace is a standalone VR educational application for subjects including Math, Physics, and Chemistry, built around a structured explore-learn-assess core loop. Students navigate a calm, minimal 3D environment to select subjects, engage with interactive episode-based lessons, and complete micro-assessments that reinforce understanding. The experience is unique in its commitment to spatial clarity over visual spectacle — every design decision prioritises learning outcomes over immersion gimmicks.

## Problem / Opportunity
Traditional e-learning platforms (video lectures, flat quiz apps) fail to leverage the spatial and interactive advantages of VR. Students disengage because passive content consumption does not build durable understanding. VR EduSpace fills the gap between passive EdTech apps and overly gamified learning toys — targeting students who need structured, curriculum-aligned content delivered in a way that makes abstract concepts (e.g., linear equations, force vectors) tangible and manipulable. The opportunity is in schools, tutoring centres, and self-directed learners who already have access to a VR headset.

## Target Players
- **Student Learner (Primary)**: Ages 12–18, moderate tech literacy, owns or has school-access to a VR headset. Wants to understand difficult STEM concepts, not just memorise them. Values fast session starts, clear progress tracking, and low frustration during navigation.
- **Self-Directed Adult Learner**: Ages 19–30, early career or university student, comfortable with technology. Uses the app independently to supplement formal education. Values depth, bookmarking, and adaptive recommendations that respect their time.
- **Educator / Parent (Secondary)**: Ages 28–50, non-VR-native. Does not directly use the app but monitors progress dashboards. Needs clear reporting, transparent curriculum coverage, and confidence that content is age-appropriate and accurate.

---

## Game Design

### Core Gameplay Loop
1. **Launch** — User enters the neutral Home Environment; last session is surfaced immediately via "Continue Learning" panel.
2. **Navigate** — User selects a Subject (Math / Physics / Chemistry) from the centre panel using gaze+tap or controller.
3. **Browse** — User opens the Episode Browser for that subject; episodes are grouped by chapter, difficulty, or recommended path.
4. **Preview** — User selects an episode tile to open the Episode Detail View; reviews objectives, prerequisites, and estimated time.
5. **Learn** — User enters the Learning Experience: Concept Explanation → Guided Interaction → Practice Task → Checkpoint.
6. **Assess** — Micro-assessments (MCQ, interactive tasks, "fix the mistake") fire after each concept chunk with instant feedback.
7. **Complete** — Episode Completion screen shows score, mastered concepts, weak areas, and time spent.
8. **Progress** — User reviews the Progress Dashboard (subject-wise, episode map, skill proficiency heatmap) and the system recommends the next episode.
9. **Loop** — User proceeds to the next episode or returns to subject selection.

### Game Mechanics
- **Gaze + Tap Selection**: Primary input method — user gazes at a UI tile for a configurable dwell time (default 1.5s) and confirms with controller trigger or hand tap; must support both 3DOF and 6DOF controllers
- **Object Manipulation**: 6DOF grab-rotate-place interactions for in-lesson objects (e.g., drag graph points, rotate molecular models, assemble physics rigs); uses Unity XR Interaction Toolkit GrabInteractable
- **Variable Simulation Control**: Slider or dial UI elements that let learners change an input value (e.g., slope, mass, temperature) and observe real-time result changes in the 3D scene
- **Answer Input — MCQ**: Floating panel with 2–4 options; gaze or ray-cast select; confirm on trigger; no timer by default [Assumed: timer is an optional educator setting]
- **Answer Input — Numeric**: Virtual keyboard or number pad rendered in world space; value confirmed with a submit button
- **Checkpoint Hint System**: If a learner answers incorrectly, a contextual hint panel appears (max 2 hints per question); third wrong attempt reveals correct answer with explanation
- **Bookmark Toggle**: Wrist UI bookmark icon saves the current episode to a Bookmarks list; persists across sessions via cloud save
- **Episode Lock/Unlock**: Episodes unlock sequentially by default within a chapter; prerequisites listed on Episode Detail View; [Assumed: educators can override lock state via a web dashboard in a future version]
- **Smooth Spatial Transitions**: Scene-to-scene transitions use a 0.5s fade-to-black or spatial zoom-out effect to reduce motion sickness; no hard cuts between environments
- **Seated + Standing Mode Toggle**: Accessible from Settings; adjusts UI panel heights and interaction ray angles for seated use (floor offset calibration)
- **Adjustable Text Size**: Three preset sizes (S / M / L) applied globally to all UI text; persists per user profile
- **Motion Comfort Options**: Teleportation locomotion (no smooth locomotion in v1); vignette toggle during any movement transitions [Assumed: snap turning with configurable angle increments (30°/45°/60°)]

### Progression System
- **Episode Completion %**: Tracked per episode; partially completed episodes resume from last checkpoint
- **Subject Mastery Score**: Aggregated from checkpoint accuracy across all episodes in a subject; displayed as 0–100% on Subject Tile
- **Difficulty Tiers**: Beginner → Intermediate → Advanced; completing lower-tier episodes unlocks upper-tier episodes within a chapter
- **Adaptive Recommendation Engine (v1 — basic)**: Post-completion, the system surfaces the next recommended episode based on completion order and weak-area heatmap data; [Assumed: ML-based adaptive path is a v2 feature; v1 uses rule-based logic]
- **Skill Proficiency Tags**: Each checkpoint question is tagged to a concept skill (e.g., "Slope Calculation"); proficiency per skill is shown in the Progress Dashboard heatmap
- **No XP or Gamification Points in v1**: [Assumed: deliberate omission to keep experience curriculum-focused; badges/XP system is out of scope for v1]

### Win / Lose Conditions
- **Episode Pass State**: Achieve ≥70% checkpoint accuracy across an episode to mark it "Completed" (green); below 70% marks it "Needs Review" (amber) [Assumed: threshold is configurable per subject by content team]
- **Episode Fail State**: Scoring below 70% does not block progression but flags the episode for review in the Progress Dashboard weak-area heatmap and triggers a "Retry recommended" prompt on the Completion Screen
- **No Hard Fail / Blocking**: Learners can always proceed to the next episode even if previous episodes are marked "Needs Review"; forced blocking is [Assumed: an optional educator lock setting deferred to v2]

---

## Visual & Audio Direction

### Art Style
Minimal, clean spatial UI design — think Apple Vision Pro spatial computing aesthetic crossed with a refined science textbook illustration style. Neutral colour palette: off-white, soft grey backgrounds, with subject-specific accent colours (Math: blue, Physics: orange, Chemistry: green). All environments are low-clutter 3D spaces — a calm floating-panel room for Home, and subject-specific minimal stages (e.g., a clean white-void lab bench for Chemistry). No fantasy, no characters, no narrative theming. Legibility and spatial comfort are the highest visual priorities. Perspective is full 3D VR (first-person). Tone is calm, intelligent, trustworthy.

### 3D / 2D Assets Required

**Environments:**
- Home Environment: Minimal neutral room with soft ambient lighting; floating panel mounting points; wrist UI anchor; subtle floor grid or gradient; no sky dome detail required
- Subject Learning Stage (shared base): Clean white-void or softly lit neutral stage used across all subjects; modular object spawn points
- Math Lesson Props: 3D coordinate grid/graph plane with moveable point handles; number line object; equation display surface
- Physics Lesson Props: Physics rig objects (ramps, pulleys, weights, springs); force arrow visualiser mesh; pendulum model
- Chemistry Lesson Props: Molecular model kit (atom sphere prefabs, bond cylinder prefabs, colour-coded by element); periodic table wall panel; beaker/flask props for reaction simulations

**Characters:**
- None in v1 [Assumed: AI Tutor avatar is a v2 feature; v1 uses text/audio feedback only]

**UI Elements:**
- Subject Tile card (with icon, progress ring, episode count, last-accessed label)
- Episode Tile card (title, duration badge, difficulty tag, lock/unlock state, completion status indicator)
- Episode Detail Panel (full-panel layout with objectives list, prerequisites, time estimate, Start/Resume/Bookmark buttons)
- Completion Screen panel (score display, concept mastery list, weak areas list, time spent, action buttons)
- Progress Dashboard panels: subject progress bars view, episode node-map view, skill heatmap grid view
- Wrist UI: compact strip with Profile icon, Progress icon, Settings icon, Bookmark icon, Home button
- Floating Quick Jump Menu: compact radial or vertical list; accessible at any point
- Checkpoint Answer Panels: MCQ layout (2–4 options), numeric keypad layout, hint reveal panel
- Loading / Transition overlay: full-field fade with optional "What you'll learn" text overlay

**VFX:**
- Hover highlight glow on interactive tiles and objects (emission pulse shader)
- Selection confirm ripple effect on UI tiles
- Correct answer particle burst (subtle green sparkle, low particle count for performance)
- Incorrect answer shake + red flash on answer panel
- Graph line update animation (lerp-drawn line when slope/variable changes)
- Atom bond formation effect (cylinder scale-in with glow when molecules assemble)
- Scene transition fade shader (full-viewport, configurable fade duration)
- Wrist UI appear/disappear animation (scale-up from wrist anchor point)

### Audio
- **Music**:
  - 1 × Home ambient track: calm, minimal lo-fi instrumental; looping; plays on Home and Subject Selection screens
  - 1 × Learning focus track: soft ambient, no melody distraction; looping; plays during active Learning Experience
  - 1 × Completion fanfare: short (3–5 sec) positive resolution sting; plays on Episode Completion screen
  - [Assumed: 3 total tracks for v1; per-subject music variants are v2]

- **SFX**:
  - UI tile hover: soft click/chime
  - UI tile select/confirm: satisfying mid-tone click
  - Episode start transition: whoosh or spatial shift tone
  - Object grab: haptic feedback trigger + soft grab sound
  - Object release/place: soft thud or click depending on object type
  - Correct answer: positive chime (non-childish; clean tone)
  - Incorrect answer: low soft buzz
  - Hint reveal: page-turn or soft pop
  - Checkpoint completion: short progression chime
  - Bookmark toggle on/off: paper-fold sound
  - Wrist UI open/close: subtle UI pop
  - Progress dashboard open: soft whoosh

---

## Technical Specifications
- **Engine**: Unity 2022 LTS (minimum); Unity 6 preferred for XR features [Assumed: confirm with dev lead]
- **Platform**: Meta Quest 2 / Quest 3 (primary); [Assumed: PC VR (Steam/Link) as secondary target; iOS/Android flat fallback is out of scope v1]
- **Target Frame Rate**: 72fps minimum (Quest 2 baseline); 90fps target (Quest 3); frame rate stability is critical for comfort — no drops below 72fps acceptable
- **Orientation**: N/A — VR headset; both seated and standing physical orientations supported via in-app mode setting
- **Min Device Spec**: Meta Quest 2 (6GB RAM, Snapdragon XR2); [Assumed: Quest Pro and Quest 3 auto-benefit from headset-side performance headroom]
- **Render Pipeline**: Universal Render Pipeline (URP) — required for Quest performance; no HDRP
- **XR Framework**: Unity XR Interaction Toolkit (XRI) 2.x or later; OpenXR backend
- **Hand Tracking**: Supported as secondary input (Meta Hand Tracking SDK); controller input is primary
- **Multiplayer**: No
- **Backend Services**:
  - User authentication (account creation, login — email/password + optional SSO) [Assumed: PlayFab or Firebase Auth]
  - Cloud save (user progress, bookmarks, settings, episode completion states)
  - Progress analytics (episode start/complete events, checkpoint accuracy, time
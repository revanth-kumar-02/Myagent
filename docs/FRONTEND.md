# Kora Desktop Frontend Architecture

The Kora desktop frontend is built using **Flutter (Linux, macOS, Windows, Web)** with a custom design system and reactive state management.

---

## 1. Design System & Theme Engine

Kora employs a warm, editorial aesthetic with two unified themes:

### Light Theme
- **Background**: Warm Ivory / Cream (`#FDFBF7`)
- **Primary**: Sage Green (`#4A6B53`)
- **Secondary**: Soft Olive (`#7D8C71`)
- **Text**: Charcoal (`#2C302E`)
- **Accent**: Muted Terracotta (`#C26D50`)
- **Surfaces**: Warm Neutral Card Surfaces (`#F7F4EC`)

### Dark Theme
- **Background**: Deep Warm Charcoal (`#191C1A`)
- **Primary**: Sage Green (`#749E7F`)
- **Secondary**: Soft Olive (`#8A9A7E`)
- **Text**: Warm Ivory (`#E8ECE9`)
- **Accent**: Terracotta (`#D9886E`)
- **Surfaces**: Dark Sage / Olive Card Surfaces (`#222724`)

Theme state is managed centrally via `ThemeProvider` and persisted across sessions.

---

## 2. Core UI Components

- **Chat & Composer**: Minimalist input composer (`[attachment] [microphone] [input] [send]`) with dynamic capability discovery, slash command tool menus, and real-time step streaming.
- **Memory & Knowledge Screen**: Transparent view of auto-learned memories, filterable by categories, with one-click forget and correction tools.
- **Plan Progress Card**: Visual breakdown of multi-step agent plans with live execution states.
- **Citation Cards**: Collapsible source badges for RAG chunks and Web search sources.

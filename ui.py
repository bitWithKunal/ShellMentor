"""
ShellMentor - ui.py  (compatibility shim)

The UI was split into three focused modules:
  - ui_core.py       shared widgets, BaseScreen, navigation, modals
  - ui_screens.py    Dashboard, Lessons, Quiz, Playground, Notes,
                     Analytics, Settings, Environment Scan
  - ui_activities.py Challenges, Challenge solver, Missions, Mission
                     runner, Achievements

This module simply re-exports the public screen/widget classes so existing
imports such as ``from ui import DashboardScreen`` keep working unchanged.
"""

from __future__ import annotations

from ui_core import (
    NavButton,
    NavigationSidebar,
    BaseScreen,
    XPBar,
    StatCard,
    SectionHeader,
    LevelUpModal,
    AchievementModal,
    HintModal,
    ConfirmModal,
)

from ui_screens import (
    DashboardScreen,
    LessonsScreen,
    QuizScreen,
    PlaygroundScreen,
    NotesScreen,
    AnalyticsScreen,
    SettingsScreen,
    EnvScanScreen,
)

from ui_activities import (
    ChallengesScreen,
    ChallengeScreen,
    MissionsScreen,
    MissionScreen,
    AchievementsScreen,
)

__all__ = [
    "NavButton",
    "NavigationSidebar",
    "BaseScreen",
    "XPBar",
    "StatCard",
    "SectionHeader",
    "LevelUpModal",
    "AchievementModal",
    "HintModal",
    "ConfirmModal",
    "DashboardScreen",
    "LessonsScreen",
    "QuizScreen",
    "PlaygroundScreen",
    "NotesScreen",
    "AnalyticsScreen",
    "SettingsScreen",
    "EnvScanScreen",
    "ChallengesScreen",
    "ChallengeScreen",
    "MissionsScreen",
    "MissionScreen",
    "AchievementsScreen",
]

# Asset Usage Map (PhillipCapital Rules)

This document outlines the standard usage of icons and logos within the application, following the established PhillipCapital branding and UI state rules.

## 1. Logos (`assets/logos/`)

Logos are categorized by their color type to maintain brand visibility across different backgrounds and themes.

| Asset Type | Files | Usage Rule |
| :--- | :--- | :--- |
| **Primary** | `Type=Primary.png`, `Type=Primary-1.png` | **Default Brand Use:** Use these as the primary logo on standard backgrounds (usually light or white). This represents the core brand colors. |
| **Monochrome (Black)** | `Type=Black.png`, `Type=Black-1.png` | **High Contrast / Grayscale:** Use these when a monochrome aesthetic is required, on very light backgrounds where the primary color lacks contrast, or for print-friendly views. |

## 2. Icons (`assets/icons/`)

Icons follow a strict state-driven naming convention to ensure consistent user feedback during interactions.

### Interaction States

| State | Files | Usage Rule |
| :--- | :--- | :--- |
| **Active (On)** | `State=On-1.png` through `State=On-25.png`, `State=on.png` | **Selected/Active:** Display these icons when a tab, button, or toggle is actively selected or turned "on". They typically feature filled shapes or primary brand colors to indicate focus. |
| **Inactive (Off)** | `State=Off-1.png` through `State=Off-23.png`, `State=off.png` | **Unselected/Default:** Use these for the default, unselected, or inactive state of interactive elements. They generally use outlines or subdued colors. |

### Sizing & Utility

| Asset | Usage Rule |
| :--- | :--- |
| `size=normal.png` | Standard sizing for general UI icons (e.g., standard buttons or navigation items). |
| `size=close_small.png` | Use for compact UI elements like small dismissal buttons on chips, banners, or modal headers. |

## Developer Guidelines
- **State Toggling:** When building interactive components like bottom navigation bars or toggle switches, always pair the corresponding `State=On` and `State=Off` assets.
- **Logo Contrast:** Always ensure the chosen logo (`Primary` vs `Black`) has sufficient contrast against its container background.

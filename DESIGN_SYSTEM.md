# PhillipCapital Design System v1.0

## 1. Brand Colors (MANDATORY)
Do not use default Flutter colors or guess hex codes. You must use these exact values:

**Primary Colors:**
- **PhillipCapital Blue (Primary):** `#00317A` (Use for primary branding, active states, and primary buttons)
- **Phillip Light Gray:** `#EEEEEE` (Use for backgrounds and secondary surfaces)
- **Phillip Gray:** `#AAAAAA` (Use for borders, disabled states, and secondary text)
- **Black:** `#000000` (Use for primary text)

**Sub-Brand / Accent Colors (Use for charts/data visualization):**
- Blue: `#0080FF`
- Cyan: `#17BCE2`
- Orange: `#F78F20`
- Green: `#14C496`
- Light Orange: `#FFBA6F`
- Pink: `#E561D2`
- Red: `#FF1515`

## 2. Typography
PhillipCapital uses two specific font families. 

**Main UI Font: 'Barlow'**
- The wide range of the Barlow font family is used as the corporate font family across all media. Use this for all standard UI, chat text, and body content.
- Available weights: Thin, Light, Regular, Medium, SemiBold, Bold.
- Note: If Barlow cannot be used, fallback to Arial, Tahoma, or Verdana.

**Logo/Display Font: 'Inter'**
- Our brand's corporate font family for logos and sub-brands is INTER. Use this strictly for massive display headers or when rendering the brand name.
- Use Inter Bold or Inter Medium.

## 3. UI Geometry (The "P" Shape)
- **Photo Frames & Containers:** Give a radius to 2 corners of the quadrilateral in photo frames to remind the user of the letter "P" (e.g., top-right and bottom-left rounded; top-left and bottom-right sharp).
- If text is added to these frames, place it on the lower left side of the frame, which is angular, to integrate the letter P.

## 4. Logo Usage Rules
- **CRITICAL:** The isolated 'P' icon is no longer part of our corporate identity and must NOT be used in any sub-brands or avatars. The "P" device must never be used in isolation.
- Always use the full "PhillipCapital" wordmark.
- Safe margins around the logo are defined by the height of the inner cavity of the letter "P".

## 5. Iconography
- **Allowed Styles:** You must ONLY use **Monotone Solid** or **Duotone Solid** icons.
- **Prohibited Styles:** Avoid using linear icons. Avoid using thin or lightweight icons to maintain visual coherence.

## Agent Implementation Instructions
1. First, create `theme.dart` applying Barlow to `TextTheme` and the Hex colors to `ColorScheme`.
2. Apply the 2-corner radius logic to custom Flutter widgets like `Container` or `Card`.
3. When selecting icons, always pull from the `assets/icons/` folder and confirm they are solid before using them.
4. When placing the brand logo, always pull the full wordmark from the `assets/logos/` folder.
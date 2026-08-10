# PPTX Template System

## Overview
Production-grade presentation generator using python-pptx with professional templates, custom fonts, and 8 slide layout types. Generates hackathon-ready pitch decks automatically from [[PPT Agent]] output.

## Downloaded Templates
All stored in `backend/assets/templates/`:

| Template | Source | Style | Layouts |
|----------|--------|-------|---------|
| `dark-modern.pptx` | [SlidesCarnival](https://www.slidescarnival.com/template/benedick-free-presentation-template/97) | Clean dark, accent colors | 9 layouts |
| `dark-dynamic-lines.pptx` | [SlidesCarnival](https://www.slidescarnival.com/template/mutius-free-presentation-template/9823) | Geometric lines, dark | 14 layouts |
| `dark-minimalist.pptx` | [SlidesCarnival](https://www.slidescarnival.com/template/dark-minimalist-slides/237927) | Ultra-minimal, green accent, Inter font | 4 layouts |
| `hendrix-dark-gradient.pptx` | [SlidesMania](https://slidesmania.com/hendrix-free-presentation-template/) | Bright gradient accents on dark | 20 layouts |

## Downloaded Fonts
All stored in `backend/assets/fonts/`:

### Modern / Presentation
| Font | Weights | Use Case |
|------|---------|----------|
| **Poppins** | Regular, Medium, SemiBold, Bold, ExtraBold + Italics | Primary heading & body |
| **Inter** | Variable weight | UI text, body copy |
| **Montserrat** | Variable weight | Alternative headings |
| **DM Sans** | Variable weight | Clean modern body |

### Technology / Futuristic
| Font | Weights | Use Case |
|------|---------|----------|
| **Space Grotesk** | Variable weight | Tech headings |
| **Rajdhani** | Light through Bold (5 weights) | Tech/geometric |
| **Orbitron** | Variable weight | Futuristic display |
| **Exo 2** | Variable weight | Tech/geometric body |

## 8 Slide Layout Types
Auto-detected from slide title keywords:

| Layout | Trigger Keywords | Design |
|--------|-----------------|--------|
| `title` | Slide #1 | 3-stop gradient, glow circles, centered title |
| `content` | introduction, problem, solution | Left accent stripe, bullet markers |
| `section_divider` | insight | Large slide number, dramatic minimal |
| `two_column` | marketing, branding, strategy | Split bordered cards |
| `stats` | viability, impact, sustainability | 3x2 stat card grid |
| `comparison` | competitive, analysis, prior art | Red vs Green side-by-side |
| `product` | product, overview | Feature cards with icons |
| `thank_you` | thank (last slide) | Centered, glow effects, branding |

## Design System
- **Backgrounds**: Deep purple gradients (`#06021A` to `#1A0E4A`)
- **Accent Colors**: Purple `#635BFF`, Teal `#0BBF8C`, Coral `#ED5F74`, Amber `#F5A623`, Cyan `#00B5D8`
- **Typography**: Poppins for headings & body
- **Decorative**: Translucent glow circles, accent bars, left stripes, card borders
- **Branding**: "AI SOFTWARE COMPANY" footer, formatted slide numbers (`01 / 10`)

## Resource Sites for Future Templates

### Free (No Signup)
- [SlidesCarnival](https://www.slidescarnival.com/) - Best free source, direct PPTX download, no limits
- [SlidesMania](https://slidesmania.com/) - Google Slides export to PPTX
- [Slidesgo](https://slidesgo.com/) - 3 free downloads/month

### Free (Account Required)
- [free-power-point-templates.com](https://www.free-power-point-templates.com/) - Social login required
- [SlideNest](https://slidenest.com/) - Free dark themes
- [SlideStack](https://slidestack.com/) - Free startup pitch decks

### Premium
- [Envato Elements](https://elements.envato.com/) - Paid, huge collection
- [SlideModel](https://slidemodel.com/) - Professional assets
- [GraphicRiver](https://graphicriver.net/) - Premium PPTX templates

### Design Inspiration
- [Pinterest](https://www.pinterest.com/ideas/dark-presentation-template/) - Dark presentation ideas
- [Dribbble](https://dribbble.com/tags/dark-presentation) - Designer portfolios
- [Behance](https://www.behance.net/) - Award-winning decks

### Assets
- [Google Fonts](https://fonts.google.com/) - Free fonts
- [Flaticon](https://www.flaticon.com/) - Icons
- [unDraw](https://undraw.co/) - Free illustrations
- [Unsplash](https://unsplash.com/) / [Pexels](https://www.pexels.com/) - Free photos

## Code Location
- Generator: `backend/app/services/pptx_generator.py`
- Templates: `backend/assets/templates/`
- Fonts: `backend/assets/fonts/`

## Related
- [[PPT Agent]] - AI agent that generates slide content
- [[Pipeline Flow]] - Where PPT generation fits in the pipeline
- [[Theme & Design]] - Frontend design system (matching colors)

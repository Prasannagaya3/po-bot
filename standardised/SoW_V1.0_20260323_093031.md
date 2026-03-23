# DesignAI

## Product Overview
DesignAI is an AI-powered kitchen design tool delivered as a Unity3D WebGL application embedded in ecommerce websites. It enables users to design, visualise, customise, and price their kitchen directly in the browser without installation. Built as a white-label SaaS platform for the Indian market, version 1 focuses exclusively on kitchen spaces.

## Problem Statement
Homeowners and renovators struggle to visualise kitchen designs before committing to purchases, leading to costly mistakes and buyer's remorse. Traditional kitchen design requires expensive in-person consultations or complex CAD software. DesignAI democratises professional kitchen design by providing an accessible, AI-assisted tool that generates personalised layouts, shows realistic 3D/AR visualisations, and provides accurate pricing—all within the browser on an ecommerce site.

## Target Users
- **Homeowners**: Need to visualise and plan kitchen renovations before purchasing; want to experiment with layouts, materials, and finishes while staying within budget
- **Kitchen Retailers/Ecommerce Operators**: Need a white-label design tool to increase customer engagement, reduce returns, and streamline the quote-to-purchase journey
- **Interior Designers**: Need to collaborate with clients on kitchen projects, share designs for approval, and generate professional quotes and technical drawings
- **Client Admins**: Need to manage product catalogs, pricing, regional configurations, and monitor business analytics

## Core Features

### Room Input & Setup (Module 1 — 2D Configurator)
- Input room layout via LiDAR scan, floorplan upload with AI extraction, manual drawing tools, or pre-built room templates
- Smart canvas with snapping, live dimensions, node editing, ruler tool, multi-select, zoom, mini-map, and undo/redo
- Drag-and-drop placement of doors and windows
- Mark fixed built-ins and utility points (gas, water, electrical) as hard constraints for AI placement
- Preference panel for setting INR budget, cabinet layout style, theme, colour palette, material preferences, ceiling height, and unit toggle (metric/imperial)
- Real-time validation engine with auto-save to local storage
- Export EnvironmentJson on continue to design generation

### AI Design Generation (Module 2)
- Processing screen showing stage labels, estimated wait time, room detection summary, and error handling
- AI generates 2–4 design variants applying all constraints (utility points, budget, theme, ergonomic rules)
- Result cards displaying thumbnail, match score, and reasoning for each variant
- Side-by-side comparison view for evaluating variants
- Regenerate all variants or lock preferred elements and regenerate others
- Mix and match elements across generated variants [Dependency: AI service boundary TBD]

### Design Editor (Module 3)
- 3D viewport with orbit, zoom, pan controls; toggle between 2D floor plan and 3D view
- Elevation views (front, side, back wall views)
- First-person walkthrough mode
- Lighting toggle with shadow rendering and undo/redo support
- Select, drag, rotate, remove, and duplicate objects
- Configure object size and type; swap objects; snap-to-grid and collision detection
- Smart spacing suggestions and placement validation
- Layer panel for managing object visibility and organisation

### Product Catalog
- Browse, search, and multi-filter catalog of cabinets, appliances, and accessories
- Fit check to validate if items fit the current design
- Real-time stock status synced from admin configurator
- Catalog API integration for clients to provide their own SKU data via standardised interface

### Finishes & Materials
- Swap finishes for shutters, flooring, backsplash, and countertops
- Moodboard panel for saving and comparing finish combinations
- QR code generated per finish for in-store reference
- Wall paint colour picker

### Pricing & Quotation
- Live pricing in INR with GST breakdown
- Quote panel showing itemised costs
- Version snapshots to save and compare pricing at different design stages

### Exports & Documentation
- Auto-generated technical drawings (floor plans, elevations)
- Bill of Materials (BOM) export
- Quote PDF export (requires authentication)
- 3D model export in GLB, FBX, and OBJ formats
- Viewport image capture

### Sharing & Collaboration
- WhatsApp sharing suite: session link, AR screenshot, PDF attachment
- View-only family link for sharing with household members
- Designer invite with role-based access
- Comment pins for annotating specific design elements
- Approval flow for client sign-off
- Keyboard shortcuts for power users

### AR Viewer (Module 4)
- WebXR support for Android devices
- Apple Quick Look support for iOS devices
- Graceful fallback to 3D spin view on unsupported devices
- 1:1 real-world scale rendering
- Floor-tap to anchor the design in physical space
- View-only mode with call-to-action to edit in main tool
- Shadows, ambient occlusion, reflections, and light simulation
- Tap objects to view name and price
- Hide/show individual items
- Annotated screenshot and video recording
- WhatsApp share from AR view

### Backend Platform
- Database with dev, staging, and production environments
- Logging, S3/CDN storage, CI/CD pipelines, and security implementation
- User authentication via SSO integration with ecommerce site and JWT tokens
- APIs for input handling (EnvironmentJson, preferences), design operations (placement, materials, updates, AR assets)
- Dynamic pricing engine with tax and discount calculations
- PDF generation for quotations
- Project lifecycle management (Draft → Completed) with task assignment
- Asset management: 3D model upload, texture mapping, CDN delivery

### Notifications
- Email, SMS, and in-app notification channels
- Triggered events: user signup, design saved, quotation generated

### Analytics & Reporting
- User behaviour tracking
- Conversion funnel analysis
- Revenue reports and dashboards

### CRM
- Lead management and tracking
- Customer profiles with interaction history

### Localisation & White-Label
- Multi-store support
- Multi-currency handling
- Multi-language support
- Regional configuration options
- White-label branding per client

### Admin Configurator
- Role-based dashboard (Client Admin and Super Admin roles)
- Catalog management: add, edit, remove products
- Texture and material management
- Pricing and tax configuration
- Store, currency, and regional settings management
- Project and quotation oversight
- CRM access and management
- Analytics dashboard

## Non-Functional Requirements
- **Platform**: Unity3D WebGL embedded in web browsers; primary target is Android mobile via Chrome 81+
- **Performance**: Minimum 30fps on mid-range Android devices (Snapdragon 600-series)
- **AI Response Time**: Design generation within 30 seconds at 95th percentile
- **Browser Support**: Chrome 81+ (covers >90% of active Android devices in India target market)
- **Connectivity**: Optimised for 4G connectivity in Tier 1 and Tier 2 Indian cities
- **Authentication**: OAuth 2.0 or JWT-based SSO integration with host ecommerce site
- **3D Assets**: White-label clients must provide GLB models for all catalog items
- **Security**: Secure API endpoints, authenticated exports, role-based access control

## Open Dependencies
- **DEP-01**: Mix and match feature boundary between AI service and Unity implementation; depends on FurnitureLayoutJson structure (Owner: AI Engineer + Unity Lead)
- **DEP-02**: Floorplan AI extraction service API contract (Owner: AI Service Team)
- **DEP-03**: Catalog API specification sign-off (Owner: Product Owner)
- **DEP-04**: SSO authentication contract from ecommerce site (Owner: Ecom Site Team)

## Out of Scope
- Room types other than Kitchen (planned for v2)
- Vastu-aware layout suggestions
- Curved walls support
- Structural columns handling
- Open cabinet interior preview
- AR measure mode
- AR editing capabilities
- Soft furnishings and décor catalog
- Native mobile applications (iOS/Android)
- Offline mode
- Purchase/checkout functionality within the tool
- Automated sync with external client ERP/inventory systems (stock managed via Admin Configurator)
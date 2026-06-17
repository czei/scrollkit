# Scrolling LED Dev Kit (SLDK) - Comprehensive Refactoring Plan

## Executive Summary

This document consolidates the plan to refactor the Theme Park Waits application to extract generic LED development functionality into a reusable library called "Scrolling LED Dev Kit" (SLDK). The library will provide a complete development environment for creating CircuitPython-based scrolling LED applications with modern development tools, debugging capabilities, and deployment features.

## Project Goals

1. **Create a reusable library** for developing scrolling LED applications
2. **Maintain compatibility** with both CircuitPython hardware and desktop development
3. **Optimize for ESP32 constraints** - ~200KB available RAM, single-core performance
4. **Provide modern development tools** including debugging, simulation, and hot-reload
5. **Enable easy deployment** with OTA updates and web-based configuration
6. **Support extensibility** through clean interfaces and plugin architecture

## ESP32-First Design Philosophy

The library follows an "ESP32-first" design approach - if it runs well on the constrained ESP32 hardware, it will run excellently in the development environment. This ensures that code written and tested on desktop will work reliably when deployed to hardware.

### ESP32/CircuitPython Constraints

The library must work within severe hardware limitations:
- **Memory**: Only ~200KB RAM available after CircuitPython loads
- **Performance**: Single-threaded, 240MHz, but Python overhead is significant  
- **Storage**: .py files loaded into RAM, so code size directly impacts available memory
- **No true multithreading**: Only cooperative async via asyncio
- **Slow I/O**: Network operations can block for seconds

## Architecture Overview

### Three-Process Architecture

The library implements a three-process async architecture for optimal performance and separation of concerns:

1. **Display Process** - Handles all display rendering at consistent frame rate
   - Runs at 50+ FPS for smooth animations
   - Never blocked by network operations
   - Consumes content from thread-safe queue
   - Manages display hardware/simulator

2. **Data Update Process** - Manages data fetching and updates in the background
   - Fetches data on configurable intervals
   - Updates content queue atomically
   - Handles API failures gracefully
   - Sends notifications to other processes

3. **Web Server Process** - Provides web UI for configuration and monitoring
   - Non-blocking web interface
   - Real-time configuration updates
   - Status monitoring and debugging
   - WebSocket support for live updates

## Hardware Support Strategy

SLDK is designed to support any CircuitPython-compatible LED matrix display through a flexible two-tier approach:

### Tier 1: Application-Specific Hardware

For custom setups, users can override the `create_display()` method in their application:

```python
class MyApp(SLDKApp):
    async def create_display(self):
        return MyCustomDisplay()  # User's hardware implementation
```

### Tier 2: Library Contributions

For widely-used hardware, device drivers are contributed to SLDK:

```python
# sldk/display/devices/new_device.py
class NewDeviceDisplay(DisplayInterface):
    # Hardware-specific implementation
```

## Implementation Phases

### Phase 1: Library Structure Setup ✅ COMPLETED

1. **Create new library repository** ✅
   - Initialize `sldk` project structure
   - Set up proper Python packaging with pyproject.toml
   - Create comprehensive README and documentation
   - Add LICENSE and contributing guidelines

2. **Extract display interfaces** ✅
   - Define DisplayInterface ABC with async methods
   - Create display content classes (ScrollingText, StaticText)
   - Implement ContentQueue for automatic content cycling
   - Add comprehensive docstrings and type hints

3. **Extract unified display logic** ✅
   - Move unified display implementation
   - Add hardware auto-detection system
   - Create device driver structure in sldk/display/devices/
   - Support for both hardware and simulator platforms

4. **Application framework** ✅
   - Create SLDKApp base class with three-process architecture
   - Implement memory-aware process spawning
   - Add create_display() override capability for custom hardware
   - Full async/await support for ESP32 compatibility

### Phase 2: Hardware Abstraction ✅ COMPLETED

5. **Multi-hardware support** ✅
   - Device driver architecture with auto-detection
   - MatrixPortal S3 device driver implementation
   - Generic displayio device driver for any CircuitPython board
   - Application-specific hardware override support

6. **Hardware contribution framework** ✅
   - Hardware developer guide and documentation
   - Device registration and detection system
   - Custom hardware examples and templates
   - Clear contribution guidelines for new devices

### Phase 3: Web Framework ✅ COMPLETED

1. **Extract web framework** ✅
   - Create generic web server base with async support
   - Define handler interface for custom endpoints
   - Move static assets framework and templates
   - Add configuration UI components

2. **Settings and configuration** ✅
   - Create settings management abstraction
   - Web-based configuration interface
   - Real-time settings updates via WebSocket
   - Configuration validation and persistence

### Phase 4: OTA Updates and Deployment ✅ COMPLETED

1. **Extract OTA system** ✅
   - Generic OTA updater for any Git repository
   - Version management and rollback capabilities
   - Progress tracking and error handling
   - Integration with web UI

2. **Deployment tools** ✅
   - .mpy compilation and optimization
   - Dependency management for CircuitPython
   - File size optimization and bundling
   - Remote deployment via web interface

### Phase 5: Advanced Features (Planned)

1. **Animation framework**
   - Advanced transition effects and easing
   - Animation composition and sequencing
   - Performance-optimized rendering pipeline
   - Custom animation plugins

2. **Plugin system**
   - Plugin discovery and loading mechanism
   - Configuration plugin interface
   - Content source plugins (RSS, APIs, sensors)
   - Display effect plugins

### Phase 6: Package Distribution (Planned)

1. **PyPI distribution**
   - Prepare package for PyPI upload
   - Add comprehensive package metadata
   - Create installation documentation
   - Set up automated releases

2. **CircuitPython Bundle**
   - Integrate with Adafruit CircuitPython Bundle
   - Optimize for memory usage on microcontrollers
   - Create bundle-specific documentation
   - Test on various CircuitPython boards

## Migration Checklist

### Pre-Migration Tasks
- [ ] Review and approve refactoring plan
- [ ] Set up new repository
- [ ] Prepare development environment

### Phase 1-2: Core Implementation ✅
- [x] Initialize library project
- [x] Extract utility modules
- [x] Define core interfaces
- [x] Extract display implementations
- [x] Create hardware abstraction

### Phase 3-4: Completed Work ✅
- [x] Extract web server framework
- [x] Build configuration framework
- [x] Migrate OTA system
- [x] Create application framework
- [x] Build development tools

### Phase 5-6: Remaining Work
- [ ] Migrate theme park app
- [ ] Comprehensive testing
- [ ] Create example applications
- [ ] Write documentation
- [ ] Package and release

## Success Metrics

1. **Adoption**: 100+ GitHub stars in 6 months
2. **Usage**: 50+ projects using the library
3. **Community**: 10+ contributors
4. **Quality**: >90% test coverage
5. **Performance**: <500KB memory footprint

## Current Status

### ✅ Completed (Phases 1-2)

**Core Infrastructure:**
- SLDK library structure with modern Python packaging
- Display abstraction layer with async support
- Three-process architecture (display, data, web)
- Memory-aware process spawning for ESP32
- Content framework (ScrollingText, StaticText, ContentQueue)
- Application framework with SLDKApp base class

**Hardware Support:**
- Two-tier hardware support (application-specific + library contributions)
- Hardware auto-detection system
- MatrixPortal S3 device driver
- Generic displayio device support
- Custom hardware override capability
- Comprehensive hardware developer documentation

**Examples and Testing:**
- Hello World example application
- Animation demo with custom content
- Custom hardware implementation example
- Basic library tests (151 unit tests still passing)
- Hardware developer guide and contribution framework

### ✅ Completed (Phases 3-4)

**Web Framework** - Complete web interface system extracted and modernized with:
- Async web server supporting both CircuitPython and development environments
- Handler interface for custom endpoints and API integration
- Configuration UI components and real-time settings management
- Static assets framework and template system

**OTA Updates** - Full over-the-air update system implemented with:
- Generic OTA updater for Git repositories with version management
- Progress tracking, error handling, and rollback capabilities
- Web-based management interface for remote updates
- File packaging, optimization, and deployment automation

### 🚧 Next Priority (Phase 5)

**Advanced Features** - Animation framework and plugin system for enhanced LED displays.
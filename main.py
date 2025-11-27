"""
SSD1309 OLED Display - Example Demonstration Script

This script demonstrates the SSD1309 OLED driver for the Raspberry Pi Pico 2.
It includes graphics demonstrations, text display, and performance testing.

================================================================================
WIRING DIAGRAM - Raspberry Pi Pico 2 to 2.42" SSD1309 OLED Module
================================================================================

    OLED Module                         Raspberry Pi Pico 2
    (7-pin header)                      
                                        
    +-----------+                       +------------------+
    |           |                       |                  |
    | GND ○-----|----------------------○| GND (Pin 38)     |
    |           |                       |                  |
    | VDD ○-----|----------------------○| 3V3 (Pin 36)     |
    |           |                       |                  |
    | SCK ○-----|----------------------○| GPIO 18 (Pin 24) | SPI0 SCK
    |           |                       |                  |
    | SDA ○-----|----------------------○| GPIO 19 (Pin 25) | SPI0 TX (MOSI)
    |           |                       |                  |
    | RST ○-----|----------------------○| GPIO 20 (Pin 26) | Reset
    |           |                       |                  |
    | DC  ○-----|----------------------○| GPIO 16 (Pin 21) | Data/Command
    |           |                       |                  |
    | CS  ○-----|----------------------○| GPIO 17 (Pin 22) | Chip Select
    |           |                       |                  |
    +-----------+                       +------------------+

Pin Summary:
    Module Pin | Function       | Pico 2 GPIO | Physical Pin | Notes
    -----------|----------------|-------------|--------------|------------------
    GND        | Ground         | GND         | 38           | Common ground
    VDD        | Logic Power    | 3.3V        | 36           | 3.3V supply
    SCK        | SPI Clock      | GPIO 18     | 24           | SPI0 SCK
    SDA        | SPI MOSI       | GPIO 19     | 25           | SPI0 TX
    RST        | Reset          | GPIO 20     | 26           | Active LOW
    DC         | Data/Command   | GPIO 16     | 21           | NOTE: Uses SPI0 RX pin
    CS         | Chip Select    | GPIO 17     | 22           | Active LOW

⚠️  CRITICAL: GPIO 16 is the default SPI0 RX (MISO) pin. Since we use it for DC,
    the SPI bus MUST be initialized with miso=None to prevent conflicts!

================================================================================
"""

import machine
import time
from ssd1309 import SSD1309_SPI


# =============================================================================
# Configuration Constants
# =============================================================================

# Display dimensions
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 64

# SPI Configuration
SPI_ID = 0
SPI_BAUDRATE = 10_000_000  # 10 MHz (max for SSD1309)
SPI_POLARITY = 0           # Clock idle LOW (Mode 0)
SPI_PHASE = 0              # Sample on rising edge (Mode 0)

# Pin assignments
PIN_SCK = 18   # SPI Clock
PIN_MOSI = 19  # SPI MOSI (labeled SDA on module)
PIN_RST = 20   # Reset (active LOW)
PIN_DC = 16    # Data/Command selection
PIN_CS = 17    # Chip Select (active LOW)


# =============================================================================
# Helper Functions
# =============================================================================

def draw_border(oled, color: int = 1) -> None:
    """
    Draw a rectangle border around the entire display.
    
    Args:
        oled: SSD1309_SPI display object.
        color: 0 for black, 1 for white.
    """
    # Draw border using rect (non-filled rectangle)
    oled.rect(0, 0, oled.width, oled.height, color)


def draw_centered_text(oled, text: str, y: int, color: int = 1) -> None:
    """
    Draw text horizontally centered on the display.
    
    Args:
        oled: SSD1309_SPI display object.
        text: Text string to display.
        y: Vertical position (top of text).
        color: 0 for black, 1 for white.
    """
    # Built-in font is 8x8 pixels
    text_width = len(text) * 8
    x = (oled.width - text_width) // 2
    oled.text(text, x, y, color)


def draw_filled_circle(oled, cx: int, cy: int, r: int, color: int = 1) -> None:
    """
    Draw a filled circle using horizontal line segments.
    
    Args:
        oled: SSD1309_SPI display object.
        cx: Center X coordinate.
        cy: Center Y coordinate.
        r: Radius in pixels.
        color: 0 for black, 1 for white.
    """
    for y in range(-r, r + 1):
        # Calculate x extent at this y using circle equation
        x_extent = int((r * r - y * y) ** 0.5)
        oled.hline(cx - x_extent, cy + y, 2 * x_extent + 1, color)


def draw_circle_outline(oled, cx: int, cy: int, r: int, color: int = 1) -> None:
    """
    Draw a circle outline using Bresenham's algorithm.
    
    Args:
        oled: SSD1309_SPI display object.
        cx: Center X coordinate.
        cy: Center Y coordinate.
        r: Radius in pixels.
        color: 0 for black, 1 for white.
    """
    x = r
    y = 0
    err = 0
    
    while x >= y:
        # Draw 8 symmetric points
        oled.pixel(cx + x, cy + y, color)
        oled.pixel(cx + y, cy + x, color)
        oled.pixel(cx - y, cy + x, color)
        oled.pixel(cx - x, cy + y, color)
        oled.pixel(cx - x, cy - y, color)
        oled.pixel(cx - y, cy - x, color)
        oled.pixel(cx + y, cy - x, color)
        oled.pixel(cx + x, cy - y, color)
        
        y += 1
        err += 1 + 2 * y
        if 2 * (err - x) + 1 > 0:
            x -= 1
            err += 1 - 2 * x


def measure_refresh_rate(oled, iterations: int = 100) -> float:
    """
    Measure display refresh performance.
    
    This function measures the time taken to refresh the display
    multiple times and calculates average performance metrics.
    
    Args:
        oled: SSD1309_SPI display object.
        iterations: Number of refresh cycles to measure.
        
    Returns:
        Average frame time in milliseconds.
        
    Target: < 15ms per frame at 10MHz SPI
    """
    # Prepare display with test pattern
    oled.fill(1)  # Fill display with white
    oled.show()   # Initial update
    
    # Measure refresh time over multiple iterations
    start = time.ticks_us()
    for _ in range(iterations):
        oled.show()
    elapsed_us = time.ticks_diff(time.ticks_us(), start)
    
    # Calculate performance metrics
    avg_time_ms = (elapsed_us / iterations) / 1000
    max_fps = 1000 / avg_time_ms if avg_time_ms > 0 else 0
    
    # Display results
    print(f"\n{'='*50}")
    print(f"Performance Test Results ({iterations} iterations):")
    print(f"{'='*50}")
    print(f"SPI Baudrate:       {SPI_BAUDRATE / 1_000_000:.1f} MHz")
    print(f"Buffer Size:        {len(oled.buffer)} bytes")
    print(f"Total Time:         {elapsed_us / 1000:.2f} ms")
    print(f"Average Frame Time: {avg_time_ms:.2f} ms")
    print(f"Maximum FPS:        {max_fps:.1f}")
    print(f"Target: < 15ms ...  {'✓ PASS' if avg_time_ms < 15 else '✗ FAIL'}")
    print(f"{'='*50}\n")
    
    return avg_time_ms


def demo_basic_shapes(oled) -> None:
    """
    Demonstrate basic shape drawing capabilities.
    
    Args:
        oled: SSD1309_SPI display object.
    """
    print("Demo 1: Basic Shapes")
    
    oled.fill(0)  # Clear display
    
    # Draw border
    draw_border(oled, 1)
    
    # Filled rectangle (top-left quadrant)
    oled.fill_rect(5, 5, 30, 20, 1)
    
    # Outlined rectangle (top-right quadrant)
    oled.rect(93, 5, 30, 20, 1)
    
    # Filled circle (bottom-left quadrant)
    draw_filled_circle(oled, 25, 48, 12, 1)
    
    # Circle outline (bottom-right quadrant)
    draw_circle_outline(oled, 103, 48, 12, 1)
    
    # Diagonal lines in center
    oled.line(50, 10, 78, 55, 1)
    oled.line(78, 10, 50, 55, 1)
    
    oled.show()
    time.sleep(2)


def demo_text(oled) -> None:
    """
    Demonstrate text display capabilities.
    
    Args:
        oled: SSD1309_SPI display object.
    """
    print("Demo 2: Text Display")
    
    oled.fill(0)  # Clear display
    draw_border(oled, 1)
    
    # Title - centered
    draw_centered_text(oled, "SSD1309 TEST", 8, 1)
    
    # Horizontal line separator
    oled.hline(10, 20, 108, 1)
    
    # Information text
    oled.text("128x64 OLED", 20, 28, 1)
    oled.text("MicroPython", 24, 40, 1)
    oled.text("Pico 2 / RP2350", 8, 52, 1)
    
    oled.show()
    time.sleep(2)


def demo_invert(oled) -> None:
    """
    Demonstrate display inversion.
    
    Args:
        oled: SSD1309_SPI display object.
    """
    print("Demo 3: Display Inversion")
    
    oled.fill(0)
    draw_centered_text(oled, "NORMAL", 28, 1)
    oled.show()
    time.sleep(1)
    
    oled.invert(True)
    time.sleep(1)
    
    oled.fill(0)
    draw_centered_text(oled, "INVERTED", 28, 1)
    oled.show()
    time.sleep(1)
    
    oled.invert(False)  # Return to normal
    time.sleep(0.5)


def demo_contrast(oled) -> None:
    """
    Demonstrate contrast adjustment.
    
    Args:
        oled: SSD1309_SPI display object.
    """
    print("Demo 4: Contrast Sweep")
    
    oled.fill(0)
    draw_border(oled, 1)
    
    # Contrast levels to demonstrate
    contrast_levels = [0, 32, 64, 128, 192, 255]
    
    for level in contrast_levels:
        oled.fill(0)
        draw_border(oled, 1)
        draw_centered_text(oled, "CONTRAST", 20, 1)
        draw_centered_text(oled, f"{level:3d}", 36, 1)
        oled.show()
        oled.contrast(level)
        time.sleep(0.5)
    
    # Reset to default contrast
    oled.contrast(0xCF)
    time.sleep(0.5)


def demo_animation(oled) -> None:
    """
    Demonstrate simple animation with a bouncing ball.
    
    Args:
        oled: SSD1309_SPI display object.
    """
    print("Demo 5: Animation (bouncing ball)")
    
    # Ball parameters
    x, y = 64, 32
    dx, dy = 3, 2
    radius = 5
    
    # Animation loop
    frames = 60
    for _ in range(frames):
        oled.fill(0)
        draw_border(oled, 1)
        
        # Draw ball
        draw_filled_circle(oled, x, y, radius, 1)
        
        # Update position
        x += dx
        y += dy
        
        # Bounce off walls
        if x <= radius + 1 or x >= oled.width - radius - 2:
            dx = -dx
        if y <= radius + 1 or y >= oled.height - radius - 2:
            dy = -dy
        
        oled.show()
    
    time.sleep(0.5)


def demo_checkerboard(oled) -> None:
    """
    Demonstrate pixel-level control with a checkerboard pattern.
    
    Args:
        oled: SSD1309_SPI display object.
    """
    print("Demo 6: Checkerboard Pattern")
    
    oled.fill(0)
    
    # Draw 8x8 checkerboard
    square_size = 8
    for row in range(oled.height // square_size):
        for col in range(oled.width // square_size):
            if (row + col) % 2 == 0:
                oled.fill_rect(
                    col * square_size,
                    row * square_size,
                    square_size,
                    square_size,
                    1
                )
    
    oled.show()
    time.sleep(2)


def demo_progress_bar(oled) -> None:
    """
    Demonstrate a progress bar animation.
    
    Args:
        oled: SSD1309_SPI display object.
    """
    print("Demo 7: Progress Bar")
    
    bar_x = 10
    bar_y = 35
    bar_width = 108
    bar_height = 16
    
    for progress in range(0, 101, 5):
        oled.fill(0)
        draw_border(oled, 1)
        draw_centered_text(oled, "Loading...", 12, 1)
        
        # Draw progress bar outline
        oled.rect(bar_x, bar_y, bar_width, bar_height, 1)
        
        # Draw filled portion
        fill_width = int((bar_width - 4) * progress / 100)
        if fill_width > 0:
            oled.fill_rect(bar_x + 2, bar_y + 2, fill_width, bar_height - 4, 1)
        
        # Draw percentage
        draw_centered_text(oled, f"{progress}%", 54, 1)
        
        oled.show()
        time.sleep(0.05)
    
    time.sleep(1)


def run_all_demos(oled) -> None:
    """
    Run all demonstration routines.
    
    Args:
        oled: SSD1309_SPI display object.
    """
    print("\n" + "="*50)
    print("SSD1309 OLED Display Demonstration")
    print("="*50 + "\n")
    
    demos = [
        demo_basic_shapes,
        demo_text,
        demo_invert,
        demo_contrast,
        demo_animation,
        demo_checkerboard,
        demo_progress_bar,
    ]
    
    for i, demo in enumerate(demos, 1):
        demo(oled)
        if i < len(demos):
            time.sleep(0.5)
    
    print("\nAll demos complete!")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """
    Main entry point - Initialize display and run demonstrations.
    """
    print("\n" + "="*50)
    print("SSD1309 OLED Driver - Initialization")
    print("="*50)
    
    # =========================================================================
    # SPI Initialization
    # =========================================================================
    # CRITICAL: Initialize with miso=None to avoid GPIO 16 conflict
    # GPIO 16 is the default SPI0 RX (MISO) pin, but we use it for DC
    
    print(f"\nInitializing SPI{SPI_ID}...")
    print(f"  Baudrate: {SPI_BAUDRATE / 1_000_000:.1f} MHz")
    print(f"  Mode: {SPI_POLARITY},{SPI_PHASE} (CPOL=0, CPHA=0)")
    print(f"  SCK:  GPIO {PIN_SCK}")
    print(f"  MOSI: GPIO {PIN_MOSI}")
    print(f"  MISO: None (GPIO 16 used for DC)")
    
    spi = machine.SPI(
        SPI_ID,
        baudrate=SPI_BAUDRATE,
        polarity=SPI_POLARITY,
        phase=SPI_PHASE,
        sck=machine.Pin(PIN_SCK),
        mosi=machine.Pin(PIN_MOSI),
        miso=None  # CRITICAL: Avoid GPIO 16 conflict
    )
    
    # =========================================================================
    # Display Initialization
    # =========================================================================
    print(f"\nInitializing display...")
    print(f"  Resolution: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")
    print(f"  RST: GPIO {PIN_RST}")
    print(f"  DC:  GPIO {PIN_DC}")
    print(f"  CS:  GPIO {PIN_CS}")
    
    try:
        oled = SSD1309_SPI(
            DISPLAY_WIDTH,
            DISPLAY_HEIGHT,
            spi,
            dc=machine.Pin(PIN_DC),
            rst=machine.Pin(PIN_RST),
            cs=machine.Pin(PIN_CS)
        )
        print("  ✓ Display initialized successfully!")
        
    except Exception as e:
        print(f"  ✗ Initialization failed: {e}")
        print("\nTroubleshooting:")
        print("  - Check all wiring connections")
        print("  - Verify VDD is connected to 3.3V")
        print("  - Ensure RST, DC, CS pins are correct")
        return
    
    # =========================================================================
    # Initial Display Test
    # =========================================================================
    print("\nRunning initial display test...")
    
    # Clear and show test pattern
    oled.fill(0)
    oled.show()
    time.sleep(0.1)
    
    # Quick visual confirmation - flash the display
    oled.fill(1)
    oled.show()
    time.sleep(0.2)
    oled.fill(0)
    oled.show()
    print("  ✓ Display responding")
    
    # =========================================================================
    # Performance Test
    # =========================================================================
    print("\nRunning performance test...")
    avg_time = measure_refresh_rate(oled, iterations=100)
    
    # =========================================================================
    # Run Demonstrations
    # =========================================================================
    run_all_demos(oled)
    
    # =========================================================================
    # Final Display
    # =========================================================================
    oled.fill(0)
    draw_border(oled, 1)
    draw_centered_text(oled, "SSD1309", 16, 1)
    draw_centered_text(oled, "READY", 32, 1)
    draw_centered_text(oled, f"{avg_time:.1f}ms refresh", 48, 1)
    oled.show()
    
    print("\n" + "="*50)
    print("Initialization complete - Display ready for use")
    print("="*50 + "\n")


# Run main if executed directly
if __name__ == "__main__":
    main()

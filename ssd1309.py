"""
SSD1309 OLED Display Driver for MicroPython (Raspberry Pi Pico 2)

A production-ready driver for 2.42-inch 128x64 OLED displays using the
SSD1309/SPD0301 controller IC over 4-wire SPI interface.

Hardware Specifications:
    - Controller: SSD1309 (Solomon Systech)
    - Resolution: 128x64 pixels (Monochrome)
    - Interface: 7-pin SPI (4-wire SPI + CS + DC + RST)
    - Logic Voltage: 3.3V
    - Panel Voltage: 8-17V (external DC-DC boost converter)

CRITICAL NOTES:
    - This driver is for SSD1309, NOT SSD1306
    - NO charge pump command (0x8D) - SSD1309 uses external boost converter
    - Command unlock (0xFD, 0x12) MUST be sent first after reset
    - SPI must be initialized with miso=None if DC pin uses GPIO 16

Typical Wiring (Pico 2):
    Module Pin | Pico 2 GPIO | Physical Pin
    -----------|-------------|-------------
    GND        | GND         | 38
    VDD        | 3.3V        | 36
    SCK        | GPIO 18     | 24
    SDA (MOSI) | GPIO 19     | 25
    RST        | GPIO 20     | 26
    DC         | GPIO 16     | 21
    CS         | GPIO 17     | 22

Example Usage:
    import machine
    from ssd1309 import SSD1309_SPI
    
    # Initialize SPI with miso=None to avoid GPIO 16 conflict
    spi = machine.SPI(0,
                      baudrate=10_000_000,
                      polarity=0,
                      phase=0,
                      sck=machine.Pin(18),
                      mosi=machine.Pin(19),
                      miso=None)
    
    # Initialize display
    oled = SSD1309_SPI(128, 64, spi,
                       dc=machine.Pin(16),
                       rst=machine.Pin(20),
                       cs=machine.Pin(17))
    
    # Draw and display
    oled.fill(0)
    oled.text("Hello!", 0, 0, 1)
    oled.show()

Troubleshooting Common Display Issues:
======================================
1. BLANK SCREEN:
   - Verify VDD = 3.3V and GND connections
   - Check SPI wiring (especially MOSI on GPIO 19)
   - Ensure command unlock (0xFD, 0x12) is sent first
   - Try increasing contrast: oled.contrast(255)
   - Verify RST pin is connected and toggling

2. UPSIDE-DOWN DISPLAY:
   - Change initialization command 0xC8 to 0xC0
   - Or modify COM_SCAN_DEC constant to 0xC0

3. MIRROR IMAGE (horizontally flipped):
   - Change initialization command 0xA1 to 0xA0
   - Or modify SEG_REMAP constant to 0xA0

4. GARBLED / INTERLEAVED LINES:
   - Change COM pins config: 0xDA, 0x12 → 0xDA, 0x02
   - Or modify COM_PINS_CONFIG constant to 0x02

5. SLOW REFRESH (> 15ms):
   - Verify SPI baudrate is 10MHz
   - Ensure show() writes entire buffer in single transaction
   - Verify miso=None in SPI initialization

6. RANDOM PIXELS / ARTIFACTS:
   - Caused by interrupted SPI transactions
   - Ensure show() always sends addressing commands (0x21, 0x22) first
   - Check for loose wiring or power supply noise

7. DISPLAY GLITCHES / BIT ERRORS:
   - Try lowering SPI speed from 10MHz to 8MHz or 4MHz
   - Improve wiring (shorter jumper wires, better breadboard contacts)

Author: Generated for Raspberry Pi Pico 2 with SSD1309 OLED
License: MIT
"""

import framebuf
import time
from micropython import const

# =============================================================================
# SSD1309 Command Definitions
# =============================================================================
# Using const() for memory optimization on microcontrollers

# Fundamental Commands
_DISPLAY_OFF = const(0xAE)          # Display OFF (sleep mode)
_DISPLAY_ON = const(0xAF)           # Display ON (normal mode)
_SET_DISPLAY_ALL_ON_RESUME = const(0xA4)  # Resume display from GDDRAM
_SET_DISPLAY_ALL_ON = const(0xA5)   # Force entire display ON (ignore RAM)
_SET_NORMAL_DISPLAY = const(0xA6)   # Normal display (0=OFF, 1=ON)
_SET_INVERTED_DISPLAY = const(0xA7) # Inverted display (0=ON, 1=OFF)

# Scrolling Commands (not used in basic driver)
_DEACTIVATE_SCROLL = const(0x2E)    # Stop scrolling

# Addressing Setting Commands
_SET_LOWER_COLUMN = const(0x00)     # Lower column start address (Page mode)
_SET_HIGHER_COLUMN = const(0x10)    # Higher column start address (Page mode)
_SET_MEMORY_MODE = const(0x20)      # Memory addressing mode
_SET_COLUMN_ADDR = const(0x21)      # Set column address (start, end)
_SET_PAGE_ADDR = const(0x22)        # Set page address (start, end)

# Hardware Configuration Commands
_SET_START_LINE = const(0x40)       # Set display start line (0-63)
_SET_SEG_REMAP = const(0xA0)        # Segment re-map (column address mapping)
_SET_SEG_REMAP_INV = const(0xA1)    # Segment re-map inverted
_SET_MULTIPLEX_RATIO = const(0xA8)  # Multiplex ratio (1 to 64)
_SET_COM_SCAN_INC = const(0xC0)     # COM output scan direction: normal
_SET_COM_SCAN_DEC = const(0xC8)     # COM output scan direction: remapped
_SET_DISPLAY_OFFSET = const(0xD3)   # Display offset (vertical shift)
_SET_COM_PINS = const(0xDA)         # COM pins hardware configuration

# Timing & Driving Scheme Commands
_SET_CLOCK_DIV = const(0xD5)        # Display clock divide ratio/oscillator
_SET_PRECHARGE = const(0xD9)        # Pre-charge period
_SET_VCOMH_DESELECT = const(0xDB)   # VCOMH deselect level
_SET_CONTRAST = const(0x81)         # Contrast control

# SSD1309-Specific Commands (NOT in SSD1306)
_SET_COMMAND_LOCK = const(0xFD)     # Command lock/unlock

# Memory Addressing Modes
_ADDR_MODE_HORIZONTAL = const(0x00)
_ADDR_MODE_VERTICAL = const(0x01)
_ADDR_MODE_PAGE = const(0x02)

# Default Configuration Values
_DEFAULT_CONTRAST = const(0xCF)     # ~80% brightness
_DEFAULT_PRECHARGE = const(0xF1)    # Phase 1: 1 DCLK, Phase 2: 15 DCLK
_DEFAULT_VCOMH = const(0x30)        # ~0.83 × VCC
_DEFAULT_CLOCK_DIV = const(0x80)    # Default oscillator frequency
_DEFAULT_COM_PINS = const(0x12)     # Alternative COM pin configuration


class SSD1309_SPI(framebuf.FrameBuffer):
    """
    SSD1309 OLED display driver using SPI interface.
    
    This class provides a complete interface for controlling SSD1309-based
    OLED displays over 4-wire SPI. It inherits from framebuf.FrameBuffer,
    providing all standard drawing methods (pixel, line, rect, fill_rect,
    text, etc.).
    
    Attributes:
        width (int): Display width in pixels.
        height (int): Display height in pixels.
        buffer (bytearray): Framebuffer storage (1024 bytes for 128x64).
        
    Note:
        The SSD1309 does NOT support the charge pump command (0x8D) used
        by SSD1306. This display uses an external DC-DC boost converter.
    """
    
    def __init__(self, width: int, height: int, spi, dc, rst, cs) -> None:
        """
        Initialize the SSD1309 display.
        
        Args:
            width: Display width in pixels (typically 128).
            height: Display height in pixels (typically 64).
            spi: Initialized machine.SPI object.
                 MUST be initialized with miso=None if using GPIO 16 for DC.
            dc: machine.Pin object for Data/Command selection.
            rst: machine.Pin object for hardware reset (active LOW).
            cs: machine.Pin object for chip select (active LOW).
            
        Raises:
            ValueError: If width/height don't match supported display sizes.
            
        Example:
            spi = machine.SPI(0, baudrate=10_000_000, polarity=0, phase=0,
                              sck=machine.Pin(18), mosi=machine.Pin(19),
                              miso=None)
            oled = SSD1309_SPI(128, 64, spi,
                               dc=machine.Pin(16),
                               rst=machine.Pin(20),
                               cs=machine.Pin(17))
        """
        # Validate dimensions
        if width != 128 or height not in (32, 64):
            raise ValueError(
                f"Unsupported display size: {width}x{height}. "
                "Supported: 128x64 or 128x32"
            )
        
        self.width = width
        self.height = height
        self.spi = spi
        
        # Configure control pins as outputs
        self.dc = dc
        self.dc.init(dc.OUT, value=0)
        
        self.rst = rst
        self.rst.init(rst.OUT, value=1)
        
        self.cs = cs
        self.cs.init(cs.OUT, value=1)
        
        # Calculate pages (8 pixels per page in vertical addressing)
        self.pages = height // 8
        
        # Create framebuffer
        # Buffer size: (width * height) / 8 = (128 * 64) / 8 = 1024 bytes
        self.buffer = bytearray(width * self.pages)
        
        # Initialize FrameBuffer with MONO_VLSB format
        # MONO_VLSB: Monochrome, vertical bytes with LSB at top
        # This matches the SSD1309's page-based memory organization
        super().__init__(self.buffer, width, height, framebuf.MONO_VLSB)
        
        # Perform full initialization sequence
        self.reset()
        self.init_display()
    
    def reset(self) -> None:
        """
        Perform hardware reset sequence.
        
        The reset sequence pulls RST LOW for 10ms (datasheet minimum is 3µs),
        then HIGH, followed by a 10ms stabilization delay. This provides a
        robust safety margin for reliable initialization.
        
        Note:
            This method is called automatically during __init__.
        """
        # Assert reset (active LOW)
        self.rst.value(1)
        time.sleep_ms(1)
        self.rst.value(0)
        time.sleep_ms(10)  # 10ms reset pulse (datasheet min: 3µs)
        
        # Release reset
        self.rst.value(1)
        time.sleep_ms(10)  # 10ms stabilization delay
    
    def write_cmd(self, cmd: int) -> None:
        """
        Send a single command byte to the display.
        
        Commands are sent with DC pin LOW, indicating command mode.
        
        Args:
            cmd: Command byte (0x00-0xFF).
        """
        self.cs.value(0)         # Select chip
        self.dc.value(0)         # Command mode
        self.spi.write(bytes([cmd]))
        self.cs.value(1)         # Deselect chip
    
    def write_data(self, buf: bytes) -> None:
        """
        Send data bytes to the display.
        
        Data is sent with DC pin HIGH, indicating data mode.
        The entire buffer is written in a single SPI transaction
        for maximum performance.
        
        Args:
            buf: Data bytes to send (typically the framebuffer).
        """
        self.cs.value(0)         # Select chip
        self.dc.value(1)         # Data mode
        self.spi.write(buf)
        self.cs.value(1)         # Deselect chip
    
    def init_display(self) -> None:
        """
        Initialize display with the complete command sequence.
        
        This method sends the full initialization sequence required for
        the SSD1309 controller. The sequence must be executed in the
        correct order for proper operation.
        
        CRITICAL: The command unlock (0xFD, 0x12) MUST be the first
        software command after hardware reset. This is mandatory for
        the SSD1309 and ensures robustness against warm reboots.
        
        Note:
            This method is called automatically during __init__.
            It does NOT include the 0x8D charge pump command, which
            is SSD1306-specific and invalid for SSD1309.
        """
        # ==== MANDATORY FIRST COMMAND: Unlock command interface ====
        # The SSD1309 has a command lock feature. We must explicitly
        # unlock it to ensure robustness against warm reboots.
        self.write_cmd(_SET_COMMAND_LOCK)  # 0xFD
        self.write_cmd(0x12)               # Unlock OLED driver IC
        
        # ==== Display OFF during initialization ====
        self.write_cmd(_DISPLAY_OFF)       # 0xAE
        
        # ==== Timing & Driving Configuration ====
        # Set display clock divide ratio and oscillator frequency
        self.write_cmd(_SET_CLOCK_DIV)     # 0xD5
        self.write_cmd(_DEFAULT_CLOCK_DIV) # 0x80 (default)
        
        # ==== Display Configuration ====
        # Set multiplex ratio (number of COM lines - 1)
        # For 64-pixel height: 64 - 1 = 63 = 0x3F
        self.write_cmd(_SET_MULTIPLEX_RATIO)  # 0xA8
        self.write_cmd(self.height - 1)       # 0x3F for 64 rows
        
        # Set display offset (vertical shift by COM)
        self.write_cmd(_SET_DISPLAY_OFFSET)   # 0xD3
        self.write_cmd(0x00)                  # No offset
        
        # Set display start line to 0
        self.write_cmd(_SET_START_LINE | 0x00)  # 0x40
        
        # ==== Memory Addressing Configuration ====
        # Set memory addressing mode to horizontal
        # Horizontal mode: column address increments, then page address
        self.write_cmd(_SET_MEMORY_MODE)      # 0x20
        self.write_cmd(_ADDR_MODE_HORIZONTAL) # 0x00
        
        # ==== Display Orientation ====
        # Segment re-map: column address 127 is mapped to SEG0
        self.write_cmd(_SET_SEG_REMAP_INV)    # 0xA1
        
        # COM output scan direction: remapped mode (COM63 to COM0)
        self.write_cmd(_SET_COM_SCAN_DEC)     # 0xC8
        
        # ==== COM Pins Hardware Configuration ====
        # Alternative COM pin configuration for 128x64 display
        self.write_cmd(_SET_COM_PINS)         # 0xDA
        self.write_cmd(_DEFAULT_COM_PINS)     # 0x12 (alternative config)
        
        # ==== Display Quality Settings ====
        # Set contrast control
        self.write_cmd(_SET_CONTRAST)         # 0x81
        self.write_cmd(_DEFAULT_CONTRAST)     # 0xCF (~80% brightness)
        
        # Set pre-charge period
        # Phase 1: 1 DCLK, Phase 2: 15 DCLK
        self.write_cmd(_SET_PRECHARGE)        # 0xD9
        self.write_cmd(_DEFAULT_PRECHARGE)    # 0xF1
        
        # Set VCOMH deselect level (~0.83 × VCC)
        self.write_cmd(_SET_VCOMH_DESELECT)   # 0xDB
        self.write_cmd(_DEFAULT_VCOMH)        # 0x30
        
        # ==== Final Display Activation ====
        # Resume display from GDDRAM content
        self.write_cmd(_SET_DISPLAY_ALL_ON_RESUME)  # 0xA4
        
        # Set normal display mode (non-inverted)
        self.write_cmd(_SET_NORMAL_DISPLAY)   # 0xA6
        
        # Deactivate scrolling (ensure clean initial state)
        self.write_cmd(_DEACTIVATE_SCROLL)    # 0x2E
        
        # Turn display ON
        self.write_cmd(_DISPLAY_ON)           # 0xAF
    
    def show(self) -> None:
        """
        Transfer the framebuffer to the display.
        
        This method copies the entire framebuffer to the display's GDDRAM.
        It first resets the addressing pointers to prevent wraparound
        artifacts from interrupted transactions.
        
        CRITICAL: The column address (0x21) and page address (0x22) commands
        MUST be sent before each buffer write. This ensures reliable updates
        even after interrupted SPI transactions.
        
        Performance:
            At 10MHz SPI, a full 1024-byte transfer takes approximately
            0.8ms for SPI transmission plus command overhead, typically
            achieving <2ms total refresh time.
        """
        # Set column address range (0-127)
        self.write_cmd(_SET_COLUMN_ADDR)  # 0x21
        self.write_cmd(0x00)              # Start column = 0
        self.write_cmd(self.width - 1)    # End column = 127
        
        # Set page address range (0-7 for 64-pixel height)
        self.write_cmd(_SET_PAGE_ADDR)    # 0x22
        self.write_cmd(0x00)              # Start page = 0
        self.write_cmd(self.pages - 1)    # End page = 7
        
        # Write entire framebuffer in single transaction
        self.write_data(self.buffer)
    
    def contrast(self, value: int) -> None:
        """
        Set display contrast (brightness).
        
        Args:
            value: Contrast level from 0 (minimum) to 255 (maximum).
                   Default initialization value is 207 (0xCF, ~80%).
                   
        Note:
            Values outside 0-255 are clamped to valid range.
        """
        # Clamp value to valid range
        value = max(0, min(255, value))
        
        self.write_cmd(_SET_CONTRAST)  # 0x81
        self.write_cmd(value)
    
    def invert(self, invert: bool) -> None:
        """
        Invert display colors.
        
        Args:
            invert: True for inverted display (0=ON, 1=OFF),
                    False for normal display (0=OFF, 1=ON).
        """
        if invert:
            self.write_cmd(_SET_INVERTED_DISPLAY)  # 0xA7
        else:
            self.write_cmd(_SET_NORMAL_DISPLAY)    # 0xA6
    
    def poweroff(self) -> None:
        """
        Put display into sleep mode (low power).
        
        In sleep mode, the display is blanked and the DC-DC converter
        is stopped, significantly reducing power consumption.
        
        Use poweron() to wake the display.
        """
        self.write_cmd(_DISPLAY_OFF)  # 0xAE
    
    def poweron(self) -> None:
        """
        Wake display from sleep mode.
        
        This restores the display to normal operation after poweroff().
        The framebuffer contents are preserved during sleep.
        """
        self.write_cmd(_DISPLAY_ON)  # 0xAF
    
    def fill(self, color: int) -> None:
        """
        Fill the entire display with a color.
        
        Args:
            color: 0 for black (OFF), 1 for white (ON).
            
        Note:
            This is inherited from FrameBuffer but documented here
            for convenience. Call show() to update the display.
        """
        super().fill(color)
    
    def pixel(self, x: int, y: int, color: int = None):
        """
        Get or set a pixel.
        
        Args:
            x: X coordinate (0 to width-1).
            y: Y coordinate (0 to height-1).
            color: If provided, sets pixel to this color (0 or 1).
                   If None, returns current pixel color.
                   
        Returns:
            Current pixel color if color argument is None.
            
        Note:
            This is inherited from FrameBuffer but documented here
            for convenience. Call show() to update the display.
        """
        return super().pixel(x, y, color)

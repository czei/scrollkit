# Connect a MatrixPortal S3 to a 64×32 LED Panel

This guide is for the physical job: taking an Adafruit MatrixPortal S3 and a
64×32 HUB75 RGB matrix panel and wiring them together. It is adapted directly
from the illustrated [ThemeParkWaits Build Your Own](https://themeparkwaits.com/products/build-your-own.html)
and [Assembly Guide](https://themeparkwaits.com/products/assembly.html).

Everything plugs together. There is no soldering, and an enclosure is optional.

## What you need

- [Adafruit MatrixPortal S3](https://www.adafruit.com/product/5778) (product
  #5778).
- [64×32 RGB LED matrix panel](https://www.adafruit.com/product/2279), 3 mm
  pitch (P3), with a HUB75 interface. The panel usually includes the gray HUB75
  ribbon cable and red/black 5 V power lead.
- [5 V USB-C power supply](https://www.adafruit.com/product/4298), rated for at
  least 3 A.
- [USB-C cable](https://www.adafruit.com/product/4473).

<figure class="setup-hero-figure">
  <img src="../../assets/setup/parts-layout.jpg" alt="A MatrixPortal S3, 64 by 32 LED panel, HUB75 ribbon cable, power leads, screws, and an optional printed enclosure laid out on a workbench">
  <figcaption>The controller, panel, ribbon cable, and power leads. The pictured enclosure and screws are optional.</figcaption>
</figure>

!!! danger "Disconnect USB power before wiring"
    Do not attach or remove the ribbon cable or power leads while the
    MatrixPortal is powered.

## Hook up the board and panel

<div class="setup-step" markdown>
<div class="setup-step__copy" markdown>

### 1. Fit the HUB75 connector to the MatrixPortal

Seat the black HUB75 ribbon-cable header firmly on the MatrixPortal's two rows
of pins. The connector is keyed and only fits in the correct orientation. Press
on the plastic housing until it is fully seated and level.

</div>
<figure class="setup-step__figure setup-step__figure--wide">
  <img src="../../assets/setup/hub75-connector.jpg" alt="The keyed black HUB75 connector being pressed onto the MatrixPortal S3 pins">
  <figcaption>Seat the keyed HUB75 connector on the MatrixPortal.</figcaption>
</figure>
</div>

<div class="setup-step" markdown>
<div class="setup-step__copy" markdown>

### 2. Connect the ribbon and power leads at the MatrixPortal

Plug one end of the gray HUB75 ribbon cable into the connector you just fitted.
Its keyed plug prevents it from being reversed.

Attach the panel's forked power leads to the MatrixPortal screw terminals:

- **Red → 5V**
- **Black → GND**

Loosen each terminal screw, slide the matching fork underneath, then tighten it
securely. Route both cables toward the LED panel without pulling on the board.

</div>
<figure class="setup-step__figure setup-step__figure--wide">
  <img src="../../assets/setup/wiring.jpg" alt="A MatrixPortal S3 with the gray HUB75 ribbon cable connected, black lead on GND, and red lead on 5V">
  <figcaption>Ribbon cable connected; black is GND and red is 5 V.</figcaption>
</figure>
</div>

<div class="setup-step" markdown>
<div class="setup-step__copy" markdown>

### 3. Connect both cables to the LED panel

On the back of the panel, plug the ribbon cable into the HUB75 **input**, not the
output. On the panel pictured here, the input is the left-hand HUB75 socket at
the tail of the printed arrows. Follow the `IN`/`OUT` labels or arrows on your
panel if its layout differs.

Press the white power plug into the panel's power socket, matching the red wires
to **VCC** and the black wires to **GND**.

</div>
<figure class="setup-step__figure setup-step__figure--wide">
  <img src="../../assets/setup/panel-back.jpg" alt="Back of a P3 64 by 32 LED panel showing the HUB75 input and the power plug aligned with VCC and GND">
  <figcaption>Use the HUB75 input and match the panel's VCC/GND markings.</figcaption>
</figure>
</div>

<div class="setup-step" markdown>
<div class="setup-step__copy" markdown>

### 4. Inspect the hookup, then connect USB-C power

Before applying power, check all four connections:

1. The HUB75 header is fully seated on the MatrixPortal.
2. The ribbon cable is keyed at both ends and uses the panel's **input**.
3. Red runs from MatrixPortal **5V** to panel **VCC**.
4. Black runs from MatrixPortal **GND** to panel **GND**.

Connect the 5 V, 3 A-or-better supply to the MatrixPortal's USB-C port. That
single connection powers both the controller and the panel.

</div>
<figure class="setup-step__figure setup-step__figure--wide">
  <img src="../../assets/setup/two-halves.jpg" alt="A MatrixPortal S3 and 64 by 32 LED panel fully joined by the HUB75 ribbon and red and black power leads">
  <figcaption>The completed MatrixPortal-to-panel hookup.</figcaption>
</figure>
</div>

## What comes next

The hardware is now assembled. A new or blank MatrixPortal will not display a
ScrollKit app until CircuitPython, the app, ScrollKit, and the required Adafruit
libraries are installed. Continue with [Deploying to hardware](../getting-started.md#deploying-to-hardware).

!!! tip "Panel stays blank after software is installed"
    Disconnect USB power, reseat the ribbon at both ends, confirm it is in the
    panel's input socket, and recheck red-to-5V/VCC and black-to-GND before
    powering it again.

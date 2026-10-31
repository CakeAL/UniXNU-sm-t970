# Firmware log exporter (Step 5)

Device commit `a4112792c2b405d053c8fd215f452b111598b66e`, framework `194aae294c1107e791f4f74b2be371a391ac6bc4`. Both trees were
clean when the commands ran.

- `verification.json`: exporter FFS GUID, FV listing evidence, FD size/digest,
  commands, and the explicit limits. `platform.json` is the committed-source
  platform check result that also asserts the DSC/FDF/library/PCD wiring.
- `firmware.log`: the normal `unixnu build firmware` run with the exporter
  staged into the pinned Mu-Silicium checkout.

What was added: `AdvancedLogDxe` in the DSC Components and FDF, the
AdvancedLoggerAccessLib/QrEncoderLib/HdwPortLib mappings, per-phase
AdvancedLoggerLib instances (SEC PeilessArm, DXE Core, DXE, Runtime, UEFI
driver/application), `BaseDebugLibAdvancedLogger` for DEBUG, and
`PcdUniXNUDeviceModel = "gts7xlwifi"`. `board.toml [payload] tools = true`
puts **Tools -> Advanced Logger** in the generated menu.

`PcdAdvancedLoggerBase` stays 0 on purpose: no fixed RAM address is fabricated
before a UEFI runtime allocation map exists. The DXE Core instance reserves the
buffer with AllocateReservedPages and installs gAdvancedLoggerProtocolGuid,
which is the exporter's Depex. SEC messages reach the panel through the hardware
port (SerialPortLib -> FrameBufferSerialPortLib in DEBUG) and are not retained in
the memory buffer.

Not verified: the Tools menu on screen, QR transfer and log contents. Building a
payload/initrd with the generated menu needs the XNU kernel and Apple payload
inputs, which this stage does not have, so `tools` is confirmed by the generator
code path only. No device write, reboot or partition change was performed.

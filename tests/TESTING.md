# Testing

## Design

The unit tests can be run with or without an EMC2101 chip connected to the
machine.

- use simulated device: `pdm run pytest`
- use hardware device: `TEST_EMC2101_CHIP=y pdm run pytest`

Mocks are used only if absolutely necessary and this enables us to run both
test scenarios with exactly the same unit tests.

## Failures

If the simulated tests succeed but the hardware tests fails then this may
indicate a misunderstanding on how the device is actually working. Please
refer to the [specification](https://ww1.microchip.com/downloads/en/DeviceDoc/2101.pdf)
to confirm understanding.

If the tests and the specification agree with each other but the tests
still fail then this may indicate an error in the specification or a
hardware fault with the chip (more likely).

import pytest

from src import MicroScope
from src.microscope import READ_ONLY_TAG, HardwareError, MicroscopeError


class TestGetProperty:
    def test_reads_demo_property_as_string(self) -> None:
        value = MicroScope()._get_property("Camera", "Exposure")
        assert isinstance(value, str)
        assert float(value) > 0

    def test_unknown_device_raises_hardware_error(self) -> None:
        with pytest.raises(HardwareError) as exc_info:
            MicroScope()._get_property("NoSuchDevice", "x")
        error = exc_info.value
        assert isinstance(error, MicroscopeError)
        assert error.label == "NoSuchDevice"
        assert error.prop == "x"
        assert isinstance(error.__cause__, RuntimeError)

    def test_unknown_property_raises_hardware_error(self) -> None:
        with pytest.raises(HardwareError) as exc_info:
            MicroScope()._get_property("Camera", "NoSuchProp")
        assert exc_info.value.prop == "NoSuchProp"


class TestDescribeDevices:
    def test_lists_every_loaded_device(self) -> None:
        microscope = MicroScope()
        report = microscope.describe_devices()
        for label in microscope.devices:
            assert label in report

    def test_read_only_properties_are_tagged(self) -> None:
        microscope = MicroScope()
        sections = microscope.describe_devices().split("\n\n")
        core = microscope.core
        for label, section in zip(microscope.devices, sections):
            lines = section.splitlines()[1:]
            for prop, line in zip(core.getDevicePropertyNames(label), lines):
                assert line.strip().startswith(prop)
                assert (READ_ONLY_TAG in line) == core.isPropertyReadOnly(label, prop)

    def test_writable_property_shows_allowed_values(self) -> None:
        microscope = MicroScope()
        report = microscope.describe_devices()
        assert "allowed: " in report

    def test_describe_allowed_list(self) -> None:
        microscope = MicroScope()
        allowed = list(microscope.core.getAllowedPropertyValues("Camera", "Binning"))
        assert microscope._describe_allowed("Camera", "Binning") == "[" + ", ".join(allowed) + "]"

    def test_describe_allowed_range_or_any(self) -> None:
        result = MicroScope()._describe_allowed("Camera", "Exposure")
        assert result.startswith("range ") or result == "any"

    def test_print_devices_prints_report(self, capsys: pytest.CaptureFixture[str]) -> None:
        microscope = MicroScope()
        microscope.print_devices()
        assert capsys.readouterr().out.strip() == microscope.describe_devices().strip()


class TestMicroScope:
    def test_microscope_initialization(self):
        # Test the initialization of the microscope object
        microscope = MicroScope()
        assert isinstance(microscope, int)

    # def test_microscope_adjust_focus(self):
    #     # Test adjusting the focus of the microscope
    #     microscope = MicroScope()
    #     initial_focus = microscope.focus_level
    #     microscope.adjust_focus(5)
    #     assert microscope.focus_level == initial_focus + 5

    # def test_microscope_set_magnification(self):
    #     # Test setting the magnification level of the microscope
    #     microscope = MicroScope()
    #     microscope.set_magnification(40)
    #     assert microscope.magnification_level == 40

    # def test_microscope_light_intensity(self):
    #     # Test adjusting the light intensity of the microscope
    #     microscope = Microscope()
    #     initial_intensity = microscope.light_intensity
    #     microscope.adjust_light_intensity(10)
    #     assert microscope.light_intensity == initial_intensity + 10
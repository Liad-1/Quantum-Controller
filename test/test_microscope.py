import pytest

from src import MicroScope
from src.microscope import HardwareError, MicroscopeError


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


class TestMicroScope:
    def test_microscope_initialization(self):
        # Test the initialization of the microscope object
        microscope = MicroScope()
        assert isinstance(microscope, MicroScope)

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
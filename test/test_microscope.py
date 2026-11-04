from src.microscope import MicroScope

class TestMicroScope:
    def test_microscope_initialization(self):
        # Test the initialization of the microscope object
        microscope = MicroScope()
        assert microscope is not None
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
#ifndef VR_MESH_RENDERER_HEADER
#define VR_MESH_RENDERER_HEADER

#include "glfw_mesh_renderer.h"
#ifdef WIN32
#include "SRanipal.h"
#include "SRanipal_Eye.h"
#include "SRanipal_Enums.h"
#endif

#include <thread>

#include <glad/gl.h>
#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>
#include <glm/gtc/type_ptr.hpp>
#include <glm/gtx/string_cast.hpp>
#include <map>
#include <openvr.h>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <queue>

namespace py = pybind11;

// Note: VR can only be used with iGibson on Windows, so we need to use a GLFW context for rendering
class VRRendererContext : public GLFWRendererContext {
public:
	// Pointer used to reference VR system
	vr::IVRSystem* m_pHMD;
	float nearClip;
	float farClip;

	// Vector indicating the user-defined offset for the VR system (may be used if implementing a teleportation movement scheme, for example)
	glm::vec3 vrOffsetVec;

	// Device data stored in VR coordinates
	struct DeviceData {
		// standard 4x4 transform
		glm::mat4 deviceTransform;
		// x,y,z
		glm::vec3 devicePos;
		// w, x, y, z (quaternion)
		glm::vec4 deviceRot;
		// is device valid and being tracked
		bool isValidData = false;
		// index of current device in device array
		int index = -1;
		// trigger pressed fraction (0 min, 1 max) - controllers only!
		float trig_frac;
		// analog touch vector - controllers only!
		glm::vec2 touchpad_analog_vec;
		// the buttons that are currently pressed, as a bit vector. bit at position i is state of button i.
		uint64_t buttons_pressed;
		// both indices are used to obtain analog data for trigger and touchpad - controllers only!
		int trigger_axis_index;
		int touchpad_axis_index;
	};

	DeviceData hmdData;
	DeviceData leftControllerData;
	DeviceData rightControllerData;

	// Indicates where the headset actually is in the room
	glm::vec3 hmdActualPos;

	// View matrices for both left and right eyes (only proj and view are actually returned to the user)
	glm::mat4 leftEyeProj;
	glm::mat4 leftEyePos;
	glm::mat4 leftEyeView;
	glm::vec3 leftEyeCameraPos;
	glm::mat4 rightEyeProj;
	glm::mat4 rightEyePos;
	glm::mat4 rightEyeView;
	glm::vec3 rightEyeCameraPos;

	// Matrices that can transform between gibson and VR space
	glm::mat4 gibToVr;
	glm::mat4 vrToGib;

	bool useEyeTracking;
	bool shouldShutDownEyeTracking;

        #ifdef WIN32
	// SRAnipal variables
	std::thread* eyeTrackingThread;
	ViveSR::anipal::Eye::EyeData eyeData;
        #endif

	int result;

	// Struct storing eye data for SR anipal - we only return origin and direction in world space
	// As most users will want to use this ray to query intersection or something similar
	struct EyeTrackingData {
		bool isValid = false;
		glm::vec3 origin;
		glm::vec3 dir;
		// Both in mm
		float leftPupilDiameter;
		float rightPupilDiameter;
	};

	EyeTrackingData eyeTrackingData;

	// Stores mapping from overlay names to handles
	std::map<std::string, vr::VROverlayHandle_t> overlayNamesToHandles;

	// Stores mapping from tracker serial names to device data
	std::map<std::string, DeviceData> trackerNamesToData;

	// Main VR methods

	VRRendererContext(int w, int h, int glVersionMajor, int glVersionMinor, bool render_window = false, bool fullscreen = false) : GLFWRendererContext(w, h, glVersionMajor, glVersionMinor, render_window, fullscreen), m_pHMD(NULL), nearClip(0.1f), farClip(30.0f) {};

	py::list getButtonDataForController(char* controllerType);

	py::list getDataForVRDevice(char* deviceType);

	py::list getDataForVRTracker(char* trackerSerialNumber);

	py::list getDeviceCoordinateSystem(char* device);

	py::list getEyeTrackingData();

	py::list getVROffset();
	
	bool hasEyeTrackingSupport();

	void initVR(bool useEyeTracking);

	py::list pollVREvents();

	void postRenderVRForEye(char* eye, GLuint texID);

	void postRenderVR(bool shouldHandoff);

	py::list preRenderVR();

	void releaseVR();

	void setVROffset(float x, float y, float z);

	void triggerHapticPulseForDevice(char* device, unsigned short microSecondDuration);

	void updateVRData();

	// VR Overlay methods

	void createOverlay(char* name, float width, float pos_x, float pos_y, float pos_z, char* fpath);

	void cropOverlay(char* name, float start_u, float start_v, float end_u, float end_v);

	void destroyOverlay(char* name);

	void hideOverlay(char* name);

	void showOverlay(char* name);

	void updateOverlayTexture(char* name, GLuint texID);
	
private:
	glm::mat4 convertSteamVRMatrixToGlmMat4(const vr::HmdMatrix34_t& matPose);

	glm::mat4 getHMDEyePose(vr::Hmd_Eye eye);

	glm::mat4 getHMDEyeProjection(vr::Hmd_Eye eye);

	glm::vec3 getPositionFromSteamVRMatrix(vr::HmdMatrix34_t& matrix);

	glm::vec4 getRotationFromSteamVRMatrix(vr::HmdMatrix34_t& matrix);

	glm::vec3 getVec3ColFromMat4(int col_index, glm::mat4& mat);

	void initAnipal();

	void pollAnipal();

	void printMat4(glm::mat4& m);

	void printVec3(glm::vec3& v);

	void processVREvent(vr::VREvent_t& vrEvent, int* controller, int* event_idx, int* press);

	void setCoordinateTransformMatrices();

	void setSteamVRMatrixPos(glm::vec3& pos, vr::HmdMatrix34_t& mat);
};

#endif

#include "vr_mesh_renderer.h"

#ifdef WIN32
#include "SRanipal.h"
#include "SRanipal_Eye.h"
#include "SRanipal_Enums.h"
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <thread>

#include <glad/egl.h>
#include <glm/glm.hpp>
#include <glm/gtc/matrix_transform.hpp>
#include <glm/gtc/type_ptr.hpp>
#include <glm/gtx/euler_angles.hpp>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

namespace py = pybind11;

// Public methods

// Get button data for a specific controller - either left_controller or right_controller
// Returns in order: trigger fraction, analog touch position x, analog touch position y, pressed buttons bitvector
// TIMELINE: Call directly after getDataForVRDevice (relies on isValid to determine data integrity)
py::list VRRendererContext::getButtonDataForController(char* controllerType) {
    DeviceData device_data;
	if (!strcmp(controllerType, "left_controller")) {
		device_data = leftControllerData;
	}
	else if (!strcmp(controllerType, "right_controller")) {
		device_data = rightControllerData;
	}

    float trigger_fraction = device_data.trig_frac;
    float touch_x = device_data.touchpad_analog_vec.x;
    float touch_y = device_data.touchpad_analog_vec.y;
    uint64_t buttons_pressed = device_data.buttons_pressed;
    bool isValid = device_data.isValidData;

	py::list buttonData;
	buttonData.append(device_data.trig_frac);
	buttonData.append(touch_x);
	buttonData.append(touch_y);
	buttonData.append(buttons_pressed);

	return buttonData;
}

// Returns device data in order: isValidData, position, rotation, hmdActualPos (valid only if hmd)
// Device type can be either hmd, left_controller or right_controller
// TIMELINE: Call at any time after postRenderVR to poll the VR system for device data
py::list VRRendererContext::getDataForVRDevice(char* deviceType) {
	bool isValid = false;

	py::array_t<float> positionData;
	py::array_t<float> rotationData;
	py::array_t<float> hmdActualPosData;

	if (!strcmp(deviceType, "hmd")) {
		glm::vec3 transformedPos(vrToGib * glm::vec4(hmdData.devicePos, 1.0));
		positionData = py::array_t<float>({ 3, }, glm::value_ptr(transformedPos));
		rotationData = py::array_t<float>({ 4, }, glm::value_ptr(vrToGib * hmdData.deviceRot));
		glm::vec3 transformedHmdPos(vrToGib * glm::vec4(hmdActualPos, 1.0));
		hmdActualPosData = py::array_t<float>({ 3, }, glm::value_ptr(transformedHmdPos));
		isValid = hmdData.isValidData;
	}
	else if (!strcmp(deviceType, "left_controller")) {
		glm::vec3 transformedPos(vrToGib * glm::vec4(leftControllerData.devicePos, 1.0));
		positionData = py::array_t<float>({ 3, }, glm::value_ptr(transformedPos));
		rotationData = py::array_t<float>({ 4, }, glm::value_ptr(vrToGib * leftControllerData.deviceRot));
		isValid = leftControllerData.isValidData;
	}
	else if (!strcmp(deviceType, "right_controller")) {
		glm::vec3 transformedPos(vrToGib * glm::vec4(rightControllerData.devicePos, 1.0));
		positionData = py::array_t<float>({ 3, }, glm::value_ptr(transformedPos));
		rotationData = py::array_t<float>({ 4, }, glm::value_ptr(vrToGib * rightControllerData.deviceRot));
		isValid = rightControllerData.isValidData;
	}

	py::list deviceData;
	deviceData.append(isValid);
	deviceData.append(positionData);
	deviceData.append(rotationData);
	deviceData.append(hmdActualPosData);

	return deviceData;
}

// Returns tracker data in order: isValidData, position, rotation
// An empty list will be returned if the input serial number is invalid
py::list VRRendererContext::getDataForVRTracker(char* trackerSerialNumber) {
	std::string trackerSerialString = std::string(trackerSerialNumber);
	bool isValid = false;
	py::list trackerData;

	py::array_t<float> positionData;
	py::array_t<float> rotationData;

	// Return empty tracker data list if the tracker serial number is invalid
	if (this->trackerNamesToData.find(trackerSerialString) != this->trackerNamesToData.end()) {
		DeviceData currTrackerData = this->trackerNamesToData[trackerSerialString];
		glm::vec3 transformedPos(vrToGib * glm::vec4(currTrackerData.devicePos, 1.0));
		positionData = py::array_t<float>({ 3, }, glm::value_ptr(transformedPos));
		rotationData = py::array_t<float>({ 4, }, glm::value_ptr(vrToGib * currTrackerData.deviceRot));
		isValid = currTrackerData.isValidData;
		trackerData.append(isValid);
		trackerData.append(positionData);
		trackerData.append(rotationData);
	}

	return trackerData;
}

// Gets normalized vectors representing HMD coordinate system
// Returns transformed x, y and z
// Represent "right", "up" and "forward" relative to headset, in iGibson coordinates
// TIMELINE: Call any time after postRenderVR
py::list VRRendererContext::getDeviceCoordinateSystem(char* device) {
	py::list vecList;
	glm::mat4 deviceTransform;

	if (!strcmp(device, "hmd")) {
		deviceTransform = hmdData.deviceTransform;
	}
	else if (!strcmp(device, "left_controller")) {
		deviceTransform = leftControllerData.deviceTransform;
	}
	else if (!strcmp(device, "right_controller")) {
		deviceTransform = rightControllerData.deviceTransform;
	}

	for (int i = 0; i < 3; i++) {
		glm::vec3 transformedVrDir = getVec3ColFromMat4(i, deviceTransform);
		if (i == 2) {
			transformedVrDir = transformedVrDir * -1.0f;
		}
		glm::vec3 transformedGibDir = glm::normalize(glm::vec3(vrToGib * glm::vec4(transformedVrDir, 1.0)));

		py::list vec;
		vec.append(transformedGibDir.x);
		vec.append(transformedGibDir.y);
		vec.append(transformedGibDir.z);
		vecList.append(vec);
	}

	return vecList;
}

// Queries eye tracking data and returns to user
// Returns in order is_data_valid, gaze origin, gaze direction, left pupil diameter (in mm), right pupil diameter (in mm)
// TIMELINE: Call after getDataForVRDevice, since this relies on knowing latest HMD transform
py::list VRRendererContext::getEyeTrackingData() {
	py::list eyeData;
	#ifdef WIN32
	// Transform data into Gibson coordinate system before returning to user
	glm::vec3 gibOrigin(vrToGib * glm::vec4(eyeTrackingData.origin, 1.0));
	glm::vec3 gibDir(vrToGib * glm::vec4(eyeTrackingData.dir, 1.0));

	py::list origin;
	origin.append(gibOrigin.x);
	origin.append(gibOrigin.y);
	origin.append(gibOrigin.z);

	py::list dir;
	dir.append(gibDir.x);
	dir.append(gibDir.y);
	dir.append(gibDir.z);
	
	// Set validity to false if eye tracking is not being used
	if (this->useEyeTracking) {
		eyeData.append(eyeTrackingData.isValid);
	}
	else {
		eyeData.append(false);
	}
	eyeData.append(origin);
	eyeData.append(dir);
	eyeData.append(eyeTrackingData.leftPupilDiameter);
	eyeData.append(eyeTrackingData.rightPupilDiameter);
	// Return dummy data with false validity if eye tracking is not enabled (on non-Windows system)
	#else
	py::list dummy_origin, dummy_dir;
	float dummy_diameter_l, dummy_diameter_r;
	eyeData.append(false);
	eyeData.append(dummy_origin);
	eyeData.append(dummy_dir);
	eyeData.append(dummy_diameter_l);
	eyeData.append(dummy_diameter_r);
	#endif
	return eyeData;
}

// Returns whether the current VR system supports eye tracking
bool VRRendererContext::hasEyeTrackingSupport() {
	#ifdef WIN32
	return ViveSR::anipal::Eye::IsViveProEye();
	// Non-windows OS always have eye tracking disabled
	#else
	return false;
	#endif
}

// Gets the VR offset vector in form x, y, z
// TIMELINE: Can call any time
py::list VRRendererContext::getVROffset() {
	glm::vec3 transformedOffsetVec(vrToGib * glm::vec4(this->vrOffsetVec, 1.0));

	py::list offset;
	offset.append(transformedOffsetVec.x);
	offset.append(transformedOffsetVec.y);
	offset.append(transformedOffsetVec.z);

	return offset;
}

// Initialize the VR system and compositor
// TIMELINE: Call during init of renderer, before height/width are set
void VRRendererContext::initVR(bool useEyeTracking) {
	// Initialize VR systems
	if (!vr::VR_IsRuntimeInstalled()) {
		fprintf(stderr, "VR runtime not installed.\n");
		exit(EXIT_FAILURE);
	}

	vr::EVRInitError eError = vr::VRInitError_None;
	m_pHMD = vr::VR_Init(&eError, vr::VRApplication_Scene);

	if (eError != vr::VRInitError_None) {
		fprintf(stderr, "Unable to initialize VR runtime.\n");
		exit(EXIT_FAILURE);
	}

	if (!vr::VRCompositor()) {
		fprintf(stderr, "Unable to intialize VR compositor.\n");
	}

	leftEyeProj = getHMDEyeProjection(vr::Eye_Left);
	leftEyePos = getHMDEyePose(vr::Eye_Left);
	rightEyeProj = getHMDEyeProjection(vr::Eye_Right);
	rightEyePos = getHMDEyePose(vr::Eye_Right);

	// Set gibToVr and vrToGib matrices
	setCoordinateTransformMatrices();
	// No VR system offset by default
	vrOffsetVec = glm::vec3(0, 0, 0);

	// Only activate eye tracking on Windows
        #ifdef WIN32
	// Set eye tracking boolean
	this->useEyeTracking = useEyeTracking;
	if (useEyeTracking) {
		shouldShutDownEyeTracking = false;
		initAnipal();
	}
        #endif
}

// Polls for VR events, such as button presses
// Guaranteed to only return valid events
// TIMELINE: Ideally call before rendering (eg. before simulator step function)
py::list VRRendererContext::pollVREvents() {
	vr::VREvent_t vrEvent;
	py::list eventData;

	while (m_pHMD->PollNextEvent(&vrEvent, sizeof(vrEvent))) {
		int controller, event_idx, press;
		processVREvent(vrEvent, &controller, &event_idx, &press);

		// -1 for controller or event indicates an invalid event
		if (controller == -1 || event_idx == -1 || press == -1) {
			continue;
		}

		py::list singleEventData;
		singleEventData.append(controller);
		singleEventData.append(event_idx);
		singleEventData.append(press);
		eventData.append(singleEventData);
	}

	return eventData;
}

// Called after the renderer has finished rendering a single eye
// TIMELINE: Call immediately after rendering for current eye is finished
void VRRendererContext::postRenderVRForEye(char* eye, GLuint texID) {
	if (!strcmp(eye, "left")) {
		vr::Texture_t leftEyeTexture = { (void*)(uintptr_t)texID, vr::TextureType_OpenGL, vr::ColorSpace_Gamma };
		vr::EVRCompositorError err = vr::VRCompositor()->Submit(vr::Eye_Left, &leftEyeTexture);
		// 0 is no error, 101 is no focus (happens at start of rendering)
		if (err != 0 && err != 101) {
			fprintf(stderr, "Compositor error: %d\n", err);
		}
	}
	else if (!strcmp(eye, "right")) {
		vr::Texture_t rightEyeTexture = { (void*)(uintptr_t)texID, vr::TextureType_OpenGL, vr::ColorSpace_Gamma };;
		vr::EVRCompositorError err = vr::VRCompositor()->Submit(vr::Eye_Right, &rightEyeTexture);
		if (err != 0 && err != 101) {
			fprintf(stderr, "Compositor error: %d\n", err);
		}
	}
}

// Called after both eyes have been rendered 
// Tell the compositor to begin work immediately instead of waiting for the next WaitGetPoses() call if the user wants
// And then update VR data
// TIMELINE: Call immediately after calling postRenderVRForEye on both left and right eyes
void VRRendererContext::postRenderVR(bool shouldHandoff) {;
	if (shouldHandoff) {
		vr::VRCompositor()->PostPresentHandoff();
	}
	// Flush rendering queue to get GPU working ASAP
	glFlush();
}

// Returns the projection and view matrices for the left and right eyes, to be used in rendering
// Also returns the camera position for each eye
// The view matrix includes a transformation that maps gibson coordinates to the VR space
// Returns in order Left P, left V, left eye camera position, right P, right V, right eye camera position
// Note: the mesh renderer expects the view matrix to be transposed, so we need to tranpose upon returning
// TIMELINE: Call before rendering so the camera is set properly
py::list VRRendererContext::preRenderVR() {
	py::array_t<float> leftEyeProjNp = py::array_t<float>({ 4,4 }, glm::value_ptr(leftEyeProj));
	py::array_t<float> rightEyeProjNp = py::array_t<float>({ 4,4 }, glm::value_ptr(rightEyeProj));

	glm::mat4 worldToHead = glm::inverse(hmdData.deviceTransform);

	leftEyeView = leftEyePos * worldToHead;
	glm::mat4 camToWorldLeft = glm::inverse(leftEyeView);
	glm::vec4 vrCamPosLeft = glm::vec4(camToWorldLeft[3][0], camToWorldLeft[3][1], camToWorldLeft[3][2], 1);
	leftEyeCameraPos = glm::vec3(vrToGib * vrCamPosLeft);

	// Once we have extracted the camera position, we can add the gibson to VR transformation matrix
	leftEyeView = leftEyeView * gibToVr;

	rightEyeView = rightEyePos * worldToHead;
	glm::mat4 camToWorldRight = glm::inverse(rightEyeView);
	glm::vec4 vrCamPosRight = glm::vec4(camToWorldRight[3][0], camToWorldRight[3][1], camToWorldRight[3][2], 1);
	rightEyeCameraPos = glm::vec3(vrToGib * vrCamPosRight);
	rightEyeView = rightEyeView * gibToVr;

	py::array_t<float> leftEyeViewNp = py::array_t<float>({ 4,4 }, glm::value_ptr(glm::transpose(leftEyeView)));
	py::array_t<float> leftEyeCameraPosNp = py::array_t<float>({ 3, }, glm::value_ptr(leftEyeCameraPos));

	py::array_t<float> rightEyeViewNp = py::array_t<float>({ 4,4 }, glm::value_ptr(glm::transpose(rightEyeView)));
	py::array_t<float> rightEyeCameraPosNp = py::array_t<float>({ 3, }, glm::value_ptr(rightEyeCameraPos));

	py::list eyeMats;
	eyeMats.append(leftEyeProjNp);
	eyeMats.append(leftEyeViewNp);
	eyeMats.append(leftEyeCameraPosNp);
	eyeMats.append(rightEyeProjNp);
	eyeMats.append(rightEyeViewNp);
	eyeMats.append(rightEyeCameraPosNp);

	return eyeMats;
}

// Releases and cleans up VR system
// TIMELINE: Call when the renderer shuts down
void VRRendererContext::releaseVR() {
	vr::VR_Shutdown();
	m_pHMD = NULL;

        #ifdef WIN32
	if (this->useEyeTracking) {
		this->shouldShutDownEyeTracking = true;
		eyeTrackingThread->join();
	}
        #endif
}

// Sets the offset of the VR headset
// TIMELINE: Can call any time
void VRRendererContext::setVROffset(float x, float y, float z) {
	this->vrOffsetVec = glm::vec3(x, y, z);
}

// Causes a haptic pulse in the specified controller, for a user-specified duration
// Note: Haptic pulses can only trigger every 5ms, regardless of duration
// TIMELINE: Call after physics/rendering have been stepped in the simulator
void VRRendererContext::triggerHapticPulseForDevice(char* device, unsigned short microSecondDuration) {
	DeviceData ddata;
	if (!strcmp(device, "hmd")) {
		ddata = hmdData;
	}
	else if (!strcmp(device, "left_controller")) {
		ddata = leftControllerData;
	}
	else if (!strcmp(device, "right_controller")) {
		ddata = rightControllerData;
	}

	if (ddata.index == -1) {
		std::cerr << "HAPTIC ERROR: Device " << device << " does not have a valid index." << std::endl;
	}

	// Currently haptics are only supported on one axis (touchpad axis)
	uint32_t hapticAxis = 0;
	m_pHMD->TriggerHapticPulse(ddata.index, hapticAxis, microSecondDuration);
}

// Calls WaitGetPoses and updates all hmd and controller transformations
void VRRendererContext::updateVRData() {
	hmdData.isValidData = false;
	leftControllerData.isValidData = false;
	rightControllerData.isValidData = false;
	// Stores controller information - see github.com/ValveSoftware/openvr/wiki/IVRSystem::GetControllerState for more info
	vr::VRControllerState_t controllerState;

	vr::TrackedDevicePose_t trackedDevices[vr::k_unMaxTrackedDeviceCount];
	vr::VRCompositor()->WaitGetPoses(trackedDevices, vr::k_unMaxTrackedDeviceCount, NULL, 0);

	for (unsigned int idx = 0; idx < vr::k_unMaxTrackedDeviceCount; idx++) {
		if (!trackedDevices[idx].bPoseIsValid || !m_pHMD->IsTrackedDeviceConnected(idx)) continue;

		vr::HmdMatrix34_t transformMat = trackedDevices[idx].mDeviceToAbsoluteTracking;
		vr::ETrackedDeviceClass trackedDeviceClass = m_pHMD->GetTrackedDeviceClass(idx);

		if (trackedDeviceClass == vr::ETrackedDeviceClass::TrackedDeviceClass_HMD) {
			hmdData.index = idx;
			hmdData.isValidData = true;
			hmdActualPos = getPositionFromSteamVRMatrix(transformMat);
                        glm::vec3 steamVrMatrixPos = hmdActualPos + vrOffsetVec;
			setSteamVRMatrixPos(steamVrMatrixPos, transformMat);

			hmdData.deviceTransform = convertSteamVRMatrixToGlmMat4(transformMat);
			hmdData.devicePos = getPositionFromSteamVRMatrix(transformMat);
			hmdData.deviceRot = getRotationFromSteamVRMatrix(transformMat);
		}
		else if (trackedDeviceClass == vr::ETrackedDeviceClass::TrackedDeviceClass_Controller) {
			vr::ETrackedControllerRole role = m_pHMD->GetControllerRoleForTrackedDeviceIndex(idx);
			if (role == vr::TrackedControllerRole_Invalid) {
				continue;
			}

			int trigger_index, touchpad_index;

			// Figures out indices that correspond with trigger and trackpad axes. Index used to read into VRControllerState_t struct array of axes.
			for (int i = 0; i < vr::k_unControllerStateAxisCount; i++) {
				int axisType = m_pHMD->GetInt32TrackedDeviceProperty(idx, (vr::ETrackedDeviceProperty)(vr::Prop_Axis0Type_Int32 + i));
				if (axisType == vr::EVRControllerAxisType::k_eControllerAxis_Trigger) {
					trigger_index = i;
				}
				// Detect trackpad on HTC Vive controller and Joystick on Oculus controller
				else if (axisType == vr::EVRControllerAxisType::k_eControllerAxis_TrackPad || axisType == vr::EVRControllerAxisType::k_eControllerAxis_Joystick) {
					touchpad_index = i;
				}
			}

			// If false, sets the controller data validity to false, as data is not valid if we can't read analog touch coordinates and trigger close fraction
			bool getControllerDataResult = m_pHMD->GetControllerState(idx, &controllerState, sizeof(controllerState));

			if (role == vr::TrackedControllerRole_LeftHand) {
				leftControllerData.index = idx;
				leftControllerData.trigger_axis_index = trigger_index;
				leftControllerData.touchpad_axis_index = touchpad_index;
				leftControllerData.isValidData = getControllerDataResult;

				glm::vec3 leftControllerPos = getPositionFromSteamVRMatrix(transformMat);
                                glm::vec3 steamVrMatrixPos = leftControllerPos + vrOffsetVec;
				setSteamVRMatrixPos(steamVrMatrixPos, transformMat);

				leftControllerData.deviceTransform = convertSteamVRMatrixToGlmMat4(transformMat);
				leftControllerData.devicePos = getPositionFromSteamVRMatrix(transformMat);
				leftControllerData.deviceRot = getRotationFromSteamVRMatrix(transformMat);

				leftControllerData.trig_frac = controllerState.rAxis[leftControllerData.trigger_axis_index].x;
				leftControllerData.touchpad_analog_vec = glm::vec2(controllerState.rAxis[leftControllerData.touchpad_axis_index].x, controllerState.rAxis[leftControllerData.touchpad_axis_index].y);
				leftControllerData.buttons_pressed = controllerState.ulButtonPressed;
			}
			else if (role == vr::TrackedControllerRole_RightHand) {
				rightControllerData.index = idx;
				rightControllerData.trigger_axis_index = trigger_index;
				rightControllerData.touchpad_axis_index = touchpad_index;
				rightControllerData.isValidData = getControllerDataResult;

				glm::vec3 rightControllerPos = getPositionFromSteamVRMatrix(transformMat);
                                glm::vec3 steamVrMatrixPos = rightControllerPos + vrOffsetVec;

				setSteamVRMatrixPos(steamVrMatrixPos, transformMat);

				rightControllerData.deviceTransform = convertSteamVRMatrixToGlmMat4(transformMat);
				rightControllerData.devicePos = getPositionFromSteamVRMatrix(transformMat);
				rightControllerData.deviceRot = getRotationFromSteamVRMatrix(transformMat);

				rightControllerData.trig_frac = controllerState.rAxis[rightControllerData.trigger_axis_index].x;
				rightControllerData.touchpad_analog_vec = glm::vec2(controllerState.rAxis[rightControllerData.touchpad_axis_index].x, controllerState.rAxis[rightControllerData.touchpad_axis_index].y);
				rightControllerData.buttons_pressed = controllerState.ulButtonPressed;
			}
		}
		else if (trackedDeviceClass == vr::ETrackedDeviceClass::TrackedDeviceClass_GenericTracker) {
			// We identify generic trackers by their serial number
			char serial_name[vr::k_unMaxPropertyStringSize];
			uint32_t serial_name_len = m_pHMD->GetStringTrackedDeviceProperty(idx, vr::ETrackedDeviceProperty::Prop_SerialNumber_String, serial_name, vr::k_unMaxPropertyStringSize);
			std::string serial(serial_name, serial_name_len-1);

			// Apply VR offset to tracker position
			glm::vec3 trackerPos = getPositionFromSteamVRMatrix(transformMat);
                        glm::vec3 steamVrMatrixPos = trackerPos + vrOffsetVec;
			setSteamVRMatrixPos(steamVrMatrixPos, transformMat);

			if (this->trackerNamesToData.find(serial) != this->trackerNamesToData.end()) {
				this->trackerNamesToData[serial].index = idx;
				this->trackerNamesToData[serial].isValidData = true;
				this->trackerNamesToData[serial].deviceTransform = convertSteamVRMatrixToGlmMat4(transformMat);
				this->trackerNamesToData[serial].devicePos = getPositionFromSteamVRMatrix(transformMat);
				this->trackerNamesToData[serial].deviceRot = getRotationFromSteamVRMatrix(transformMat);
			}
			else {
				DeviceData trackerData;
				trackerData.index = idx;
				trackerData.isValidData = true;
				trackerData.deviceTransform = convertSteamVRMatrixToGlmMat4(transformMat);
				trackerData.devicePos = getPositionFromSteamVRMatrix(transformMat);
				trackerData.deviceRot = getRotationFromSteamVRMatrix(transformMat);
				this->trackerNamesToData[serial] = trackerData;
			}
		}
	}
}

// VR overlay methods
void VRRendererContext::createOverlay(char* name, float width, float pos_x, float pos_y, float pos_z, char* fpath) {
	vr::VROverlayHandle_t handle;
	vr::VROverlay()->CreateOverlay(name, name, &handle);
	if (strcmp(fpath, "") != 0) {
		vr::VROverlay()->SetOverlayFromFile(handle, fpath);
	}
	vr::VROverlay()->SetOverlayWidthInMeters(handle, width);
	
	vr::HmdMatrix34_t transform = {
		1.0f, 0.0f, 0.0f, pos_x,
		0.0f, 1.0f, 0.0f, pos_y,
		0.0f, 0.0f, 1.0f, pos_z
	};
	std::string ovName = std::string(name);
	this->overlayNamesToHandles[ovName] = handle;

	vr::VROverlayError overlayError = vr::VROverlay()->SetOverlayTransformTrackedDeviceRelative(handle, vr::k_unTrackedDeviceIndex_Hmd, &transform);
	if (overlayError != vr::VROverlayError_None) {
		std::cerr << "VR OVERLAY ERROR: unable to set overlay relative to HMD for name " << ovName << std::endl;
	}
}

void VRRendererContext::cropOverlay(char* name, float start_u, float start_v, float end_u, float end_v) {
	std::string ovName(name);
	vr::VROverlayHandle_t handle = this->overlayNamesToHandles[ovName];

	// Create texture bounds and crop overlay
	vr::VRTextureBounds_t texBounds;
	texBounds.uMin = start_u;
	texBounds.vMin = start_v;
	texBounds.uMax = end_u;
	texBounds.vMax = end_v;

	vr::VROverlayError overlayError = vr::VROverlay()->SetOverlayTextureBounds(handle, &texBounds);
	if (overlayError != vr::VROverlayError_None) {
		std::cerr << "VR OVERLAY ERROR: unable to crop overlay with name " << ovName << std::endl;
	}
}

void VRRendererContext::destroyOverlay(char* name) {
	std::string ovName(name);
	vr::VROverlayHandle_t handle = this->overlayNamesToHandles[ovName];
	vr::VROverlayError overlayError = vr::VROverlay()->DestroyOverlay(handle);
	if (overlayError != vr::VROverlayError_None) {
		std::cerr << "VR OVERLAY ERROR: unable to destroy overlay with name " << ovName << std::endl;
	}
}

void VRRendererContext::hideOverlay(char* name) {
	vr::VROverlay()->HideOverlay(this->overlayNamesToHandles[std::string(name)]);
}

void VRRendererContext::showOverlay(char* name) {
	vr::VROverlay()->ShowOverlay(this->overlayNamesToHandles[std::string(name)]);
}

void VRRendererContext::updateOverlayTexture(char* name, GLuint texID) {
	vr::Texture_t texture = { (void*)(uintptr_t)texID, vr::TextureType_OpenGL, vr::ColorSpace_Auto };
	vr::VROverlayError overlayError = vr::VROverlay()->SetOverlayTexture(this->overlayNamesToHandles[std::string(name)], &texture);
	if (overlayError != vr::VROverlayError_None) {
		std::cerr << "VR OVERLAY ERROR: unable to set texture for overlay with name " << std::string(name) << std::endl;
	}
}

// Private methods

// Converts a SteamVR Matrix to a glm mat4
glm::mat4 VRRendererContext::convertSteamVRMatrixToGlmMat4(const vr::HmdMatrix34_t& matPose) {
	glm::mat4 mat(
		matPose.m[0][0], matPose.m[1][0], matPose.m[2][0], 0.0,
		matPose.m[0][1], matPose.m[1][1], matPose.m[2][1], 0.0,
		matPose.m[0][2], matPose.m[1][2], matPose.m[2][2], 0.0,
		matPose.m[0][3], matPose.m[1][3], matPose.m[2][3], 1.0f
	);
	return mat;
}

// Generates a pose matrix for the specified eye (left or right)
glm::mat4 VRRendererContext::getHMDEyePose(vr::Hmd_Eye eye) {
	vr::HmdMatrix34_t mat = m_pHMD->GetEyeToHeadTransform(eye);

	glm::mat4 eyeToHead(
		mat.m[0][0], mat.m[1][0], mat.m[2][0], 0.0,
		mat.m[0][1], mat.m[1][1], mat.m[2][1], 0.0,
		mat.m[0][2], mat.m[1][2], mat.m[2][2], 0.0,
		mat.m[0][3], mat.m[1][3], mat.m[2][3], 1.0f
	);

	// Return the head to eye transform
	return glm::inverse(eyeToHead);
}

// Generates a projection matrix for the specified eye (left or right)
glm::mat4 VRRendererContext::getHMDEyeProjection(vr::Hmd_Eye eye) {
	vr::HmdMatrix44_t mat = m_pHMD->GetProjectionMatrix(eye, nearClip, farClip);

	glm::mat4 eyeProjMat(
		mat.m[0][0], mat.m[1][0], mat.m[2][0], mat.m[3][0],
		mat.m[0][1], mat.m[1][1], mat.m[2][1], mat.m[3][1],
		mat.m[0][2], mat.m[1][2], mat.m[2][2], mat.m[3][2],
		mat.m[0][3], mat.m[1][3], mat.m[2][3], mat.m[3][3]
	);

	return eyeProjMat;
}

// Gets position of HMD
glm::vec3 VRRendererContext::getPositionFromSteamVRMatrix(vr::HmdMatrix34_t& matrix) {
	return glm::vec3(matrix.m[0][3], matrix.m[1][3], matrix.m[2][3]);
}

// Gets rotation of HMD in vec4 form
glm::vec4 VRRendererContext::getRotationFromSteamVRMatrix(vr::HmdMatrix34_t& matrix) {
	glm::vec4 q;

	q.w = (float)sqrt(fmax(0, 1 + matrix.m[0][0] + matrix.m[1][1] + matrix.m[2][2])) / 2;
	q.x = (float)sqrt(fmax(0, 1 + matrix.m[0][0] - matrix.m[1][1] - matrix.m[2][2])) / 2;
	q.y = (float)sqrt(fmax(0, 1 - matrix.m[0][0] + matrix.m[1][1] - matrix.m[2][2])) / 2;
	q.z = (float)sqrt(fmax(0, 1 - matrix.m[0][0] - matrix.m[1][1] + matrix.m[2][2])) / 2;
	q.x = copysign(q.x, matrix.m[2][1] - matrix.m[1][2]);
	q.y = copysign(q.y, matrix.m[0][2] - matrix.m[2][0]);
	q.z = copysign(q.z, matrix.m[1][0] - matrix.m[0][1]);

	return q;
}

// Gets vector 3 representation of column from glm mat 4
	// Useful for extracting rotation component from matrix
glm::vec3 VRRendererContext::getVec3ColFromMat4(int col_index, glm::mat4& mat) {
	glm::vec3 v;
	v.x = mat[col_index][0];
	v.y = mat[col_index][1];
	v.z = mat[col_index][2];

	return v;
}

#ifdef WIN32
// Initializes the SRAnipal runtime, if the user selects this option
void VRRendererContext::initAnipal() {
	if (!ViveSR::anipal::Eye::IsViveProEye()) {
		fprintf(stderr, "This HMD does not support eye-tracking!\n");
		exit(EXIT_FAILURE);
	}

	int anipalError = ViveSR::anipal::Initial(ViveSR::anipal::Eye::ANIPAL_TYPE_EYE, NULL);
	switch (anipalError) {
	case ViveSR::Error::WORK:
		break;
	case ViveSR::Error::RUNTIME_NOT_FOUND:
		fprintf(stderr, "SRAnipal runtime not found!\n");
		exit(EXIT_FAILURE);
	default:
		fprintf(stderr, "Failed to initialize SRAnipal!\n");
		exit(EXIT_FAILURE);
	}

	// Launch a thread to poll data from the SRAnipal SDK
	// We poll data asynchronously so as to not slow down the VR rendering loop
	eyeTrackingThread = new std::thread(&VRRendererContext::pollAnipal, this);
}

// Polls SRAnipal to get updated eye tracking information
// See this forum discussion to learn how the coordinate systems of OpenVR and SRAnipal are related: 
// https://forum.vive.com/topic/5888-vive-pro-eye-finding-a-single-eye-origin-in-world-space/?ct=1593593815
// Uses right-handed coordinate system with +ve x left, +ve z forward and +ve y up
// We need to convert that to a +ve x right, +ve z backward and +ve y up system at the end of the function
void VRRendererContext::pollAnipal() {
	while (!this->shouldShutDownEyeTracking) {
		this->result = ViveSR::anipal::Eye::GetEyeData(&this->eyeData);
		if (result == ViveSR::Error::WORK) {
			int isOriginValid = ViveSR::anipal::Eye::DecodeBitMask(this->eyeData.verbose_data.combined.eye_data.eye_data_validata_bit_mask,
				ViveSR::anipal::Eye::SINGLE_EYE_DATA_GAZE_DIRECTION_VALIDITY);
			int isDirValid = ViveSR::anipal::Eye::DecodeBitMask(this->eyeData.verbose_data.combined.eye_data.eye_data_validata_bit_mask,
				ViveSR::anipal::Eye::SINGLE_EYE_DATA_GAZE_ORIGIN_VALIDITY);
			if (!isOriginValid || !isDirValid) {
				eyeTrackingData.isValid = false;
				continue;
			}

			eyeTrackingData.isValid = true;

			// Both origin and dir are relative to the HMD coordinate system, so we need to transform them into HMD coordinate system
			if (!hmdData.isValidData) {
				eyeTrackingData.isValid = false;
				continue;
			}

			// Returns value in mm, so need to divide by 1000 to get meters (Gibson uses meters)
			auto gazeOrigin = this->eyeData.verbose_data.combined.eye_data.gaze_origin_mm;
			if (gazeOrigin.x == -1.0f && gazeOrigin.y == -1.0f && gazeOrigin.z == -1.0f) {
				eyeTrackingData.isValid = false;
				continue;
			}
			glm::vec3 eyeSpaceOrigin(-1 * gazeOrigin.x / 1000.0f, gazeOrigin.y / 1000.0f, -1 * gazeOrigin.z / 1000.0f);
			eyeTrackingData.origin = glm::vec3(hmdData.deviceTransform * glm::vec4(eyeSpaceOrigin, 1.0));

			auto gazeDirection = this->eyeData.verbose_data.combined.eye_data.gaze_direction_normalized;
			if (gazeDirection.x == -1.0f && gazeDirection.y == -1.0f && gazeDirection.z == -1.0f) {
				eyeTrackingData.isValid = false;
				continue;
			}

			// Convert to OpenVR coordinates
			glm::vec3 eyeSpaceDir(-1 * gazeDirection.x, gazeDirection.y, -1 * gazeDirection.z);

			// Only rotate, no translate - remove translation to preserve rotation
			glm::vec3 hmdSpaceDir(hmdData.deviceTransform * glm::vec4(eyeSpaceDir, 1.0));
			// Make sure to normalize (and also flip x and z, since anipal coordinate convention is different to OpenGL)
			eyeTrackingData.dir = glm::normalize(glm::vec3(hmdSpaceDir.x - hmdData.devicePos.x, hmdSpaceDir.y - hmdData.devicePos.y, hmdSpaceDir.z - hmdData.devicePos.z));

			// Record pupil measurements
			eyeTrackingData.leftPupilDiameter = this->eyeData.verbose_data.left.pupil_diameter_mm;
			eyeTrackingData.rightPupilDiameter = this->eyeData.verbose_data.right.pupil_diameter_mm;
		}
	}
}
#endif

// Print string version of mat4 for debugging purposes
void VRRendererContext::printMat4(glm::mat4& m) {
	printf(glm::to_string(m).c_str());
	printf("\n");
}

// Print string version of vec3 for debugging purposes
void VRRendererContext::printVec3(glm::vec3& v) {
	printf(glm::to_string(v).c_str());
	printf("\n");
}

// Processes a single VR event
// Controller: -1 (invalid), 0 (left controller), 1 (right controller)
// Event idx: integer given by EVRButtonId enum in openvr.h header file
// Press: -1 (invalid), 0 (for unpress/untouch), 1 (for press/touch)
void VRRendererContext::processVREvent(vr::VREvent_t& vrEvent, int* controller, int* event_idx, int* press) {
	vr::ETrackedDeviceClass trackedDeviceClass = m_pHMD->GetTrackedDeviceClass(vrEvent.trackedDeviceIndex);

	// Exit if we found a non-controller event
	if (trackedDeviceClass != vr::ETrackedDeviceClass::TrackedDeviceClass_Controller) {
		*controller = -1;
		return;
	}

	vr::ETrackedControllerRole role = m_pHMD->GetControllerRoleForTrackedDeviceIndex(vrEvent.trackedDeviceIndex);
	if (role == vr::TrackedControllerRole_Invalid) {
		*controller = -1;
	}
	else if (role == vr::TrackedControllerRole_LeftHand) {
		*controller = 0;
	}
	else if (role == vr::TrackedControllerRole_RightHand) {
		*controller = 1;
	}

	*event_idx = vrEvent.data.controller.button;
	// Both ButtonPress and ButtonTouch count as "press" (same goes for unpress/untouch)
	int press_id = vrEvent.eventType;
	if (press_id == vr::VREvent_ButtonUnpress || press_id == vr::VREvent_ButtonUntouch) {
		*press = 0;
	}
	else if (press_id == vr::VREvent_ButtonPress || press_id == vr::VREvent_ButtonTouch) {
		*press = 1;
	}
	else {
		*press = -1;
	}
}

// Sets coordinate transform matrices
void VRRendererContext::setCoordinateTransformMatrices() {
	gibToVr[0] = glm::vec4(0.0, 0.0, -1.0, 0.0);
	gibToVr[1] = glm::vec4(-1.0, 0.0, 0.0, 0.0);
	gibToVr[2] = glm::vec4(0.0, 1.0, 0.0, 0.0);
	gibToVr[3] = glm::vec4(0.0, 0.0, 0.0, 1.0);

	vrToGib[0] = glm::vec4(0.0, -1.0, 0.0, 0.0);
	vrToGib[1] = glm::vec4(0.0, 0.0, 1.0, 0.0);
	vrToGib[2] = glm::vec4(-1.0, 0.0, 0.0, 0.0);
	vrToGib[3] = glm::vec4(0.0, 0.0, 0.0, 1.0);
}

// Sets the position component of a SteamVR Matrix
void VRRendererContext::setSteamVRMatrixPos(glm::vec3& pos, vr::HmdMatrix34_t& mat) {
	mat.m[0][3] = pos[0];
	mat.m[1][3] = pos[1];
	mat.m[2][3] = pos[2];
}

PYBIND11_MODULE(VRRendererContext, m) {

	py::class_<VRRendererContext> pymodule = py::class_<VRRendererContext>(m, "VRRendererContext");

	pymodule.def(py::init<int, int, int, int, bool, bool>());
	pymodule.def("init", &VRRendererContext::init);
	pymodule.def("release", &VRRendererContext::release);
	pymodule.def("render_companion_window_from_buffer", &VRRendererContext::render_companion_window_from_buffer);

	// class MeshRenderer
	pymodule.def("render_meshrenderer_pre", &VRRendererContext::render_meshrenderer_pre,
		"pre-executed functions in MeshRenderer.render");
	pymodule.def("render_meshrenderer_post", &VRRendererContext::render_meshrenderer_post,
		"post-executed functions in MeshRenderer.render");
	pymodule.def("getstring_meshrenderer", &VRRendererContext::getstring_meshrenderer, "return GL version string");
	pymodule.def("readbuffer_meshrenderer", &VRRendererContext::readbuffer_meshrenderer, "read pixel buffer");
	pymodule.def("readbuffer_meshrenderer_shadow_depth", &VRRendererContext::readbuffer_meshrenderer_shadow_depth,
		"read pixel buffer");
	pymodule.def("clean_meshrenderer", &VRRendererContext::clean_meshrenderer, "clean meshrenderer");
	pymodule.def("setup_framebuffer_meshrenderer", &VRRendererContext::setup_framebuffer_meshrenderer,
		"setup framebuffer in meshrenderer");
	pymodule.def("setup_pbr", &VRRendererContext::setup_pbr, "setup pbr");

	pymodule.def("setup_framebuffer_meshrenderer_ms", &VRRendererContext::setup_framebuffer_meshrenderer_ms,
		"setup framebuffer in meshrenderer with MSAA");
	pymodule.def("blit_buffer", &VRRendererContext::blit_buffer, "blit buffer");

	pymodule.def("compile_shader_meshrenderer", &VRRendererContext::compile_shader_meshrenderer,
		"compile vertex and fragment shader");
	pymodule.def("load_object_meshrenderer", &VRRendererContext::load_object_meshrenderer,
		"load object into VAO and VBO");
	pymodule.def("loadTexture", &VRRendererContext::loadTexture, "load texture function");
	pymodule.def("allocateTexture", &VRRendererContext::allocateTexture, "load texture function");
	pymodule.def("updateTextureIdArrays", &VRRendererContext::updateTextureIdArrays);

	// class Instance
	pymodule.def("render_softbody_instance", &VRRendererContext::render_softbody_instance,
		"render softbody in instance.render");
	pymodule.def("initvar", &VRRendererContext::initvar, "init uniforms in instance.render");
	pymodule.def("init_material_instance", &VRRendererContext::init_material_instance,
		"init materials in instance.render");
	pymodule.def("draw_elements_instance", &VRRendererContext::draw_elements_instance,
		"draw elements in instance.render and instancegroup.render");

	// class InstanceGroup
	pymodule.def("init_pos_instance", &VRRendererContext::init_pos_instance,
		"init position in instancegroup.render");

	// misc
	pymodule.def("cglBindVertexArray", &VRRendererContext::cglBindVertexArray, "binding function");
	pymodule.def("cglUseProgram", &VRRendererContext::cglUseProgram, "binding function");

	// for optimized renderer
	pymodule.def("generateArrayTextures", &VRRendererContext::generateArrayTextures, "TBA");
	pymodule.def("renderSetup", &VRRendererContext::renderSetup, "TBA");
	pymodule.def("updateHiddenData", &VRRendererContext::updateHiddenData, "TBA");
	pymodule.def("updateUVData", &VRRendererContext::updateUVData, "TBA");
	pymodule.def("updateDynamicData", &VRRendererContext::updateDynamicData, "TBA");
	pymodule.def("renderOptimized", &VRRendererContext::renderOptimized, "TBA");
	pymodule.def("clean_meshrenderer_optimized", &VRRendererContext::clean_meshrenderer_optimized, "TBA");

	// for skybox
	pymodule.def("loadSkyBox", &VRRendererContext::loadSkyBox, "TBA");
	pymodule.def("renderSkyBox", &VRRendererContext::renderSkyBox, "TBA");

	// for text
	pymodule.def("loadCharTexture", &VRRendererContext::loadCharTexture, "TBA");
	pymodule.def("setupTextRender", &VRRendererContext::setupTextRender, "TBA");
	pymodule.def("preRenderTextFramebufferSetup", &VRRendererContext::preRenderTextFramebufferSetup, "TBA");
	pymodule.def("preRenderText", &VRRendererContext::preRenderText, "TBA");
	pymodule.def("renderChar", &VRRendererContext::renderChar, "TBA");
	pymodule.def("postRenderText", &VRRendererContext::postRenderText, "TBA");
	pymodule.def("genTextFramebuffer", &VRRendererContext::genTextFramebuffer, "TBA");
	pymodule.def("renderBackgroundQuad", &VRRendererContext::renderBackgroundQuad, "TBA");
	pymodule.def("read_fbo_color_tex_to_numpy", &VRRendererContext::read_fbo_color_tex_to_numpy, "TBA");

	// VR functions
	pymodule.def("getButtonDataForController", &VRRendererContext::getButtonDataForController);
	pymodule.def("getDataForVRDevice", &VRRendererContext::getDataForVRDevice);
	pymodule.def("getDataForVRTracker", &VRRendererContext::getDataForVRTracker);
	pymodule.def("getDeviceCoordinateSystem", &VRRendererContext::getDeviceCoordinateSystem);
	pymodule.def("getEyeTrackingData", &VRRendererContext::getEyeTrackingData);
	pymodule.def("hasEyeTrackingSupport", &VRRendererContext::hasEyeTrackingSupport);
	pymodule.def("getVROffset", &VRRendererContext::getVROffset);
	pymodule.def("initVR", &VRRendererContext::initVR);
	pymodule.def("pollVREvents", &VRRendererContext::pollVREvents);
	pymodule.def("postRenderVRForEye", &VRRendererContext::postRenderVRForEye);
	pymodule.def("postRenderVR", &VRRendererContext::postRenderVR);
	pymodule.def("preRenderVR", &VRRendererContext::preRenderVR);
	pymodule.def("releaseVR", &VRRendererContext::releaseVR);
	pymodule.def("setVROffset", &VRRendererContext::setVROffset);
	pymodule.def("triggerHapticPulseForDevice", &VRRendererContext::triggerHapticPulseForDevice);
	pymodule.def("updateVRData", &VRRendererContext::updateVRData);

	// VR overlay methods
	pymodule.def("createOverlay", &VRRendererContext::createOverlay);
	pymodule.def("cropOverlay", &VRRendererContext::cropOverlay);
	pymodule.def("destroyOverlay", &VRRendererContext::destroyOverlay);
	pymodule.def("hideOverlay", &VRRendererContext::hideOverlay);
	pymodule.def("showOverlay", &VRRendererContext::showOverlay);
	pymodule.def("updateOverlayTexture", &VRRendererContext::updateOverlayTexture);

	// verbosity
	pymodule.def_readwrite("verbosity", &VRRendererContext::verbosity);

#ifdef VERSION_INFO
	m.attr("__version__") = VERSION_INFO;
#else
	m.attr("__version__") = "dev";
#endif
}

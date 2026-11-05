idf_component_register(
    SRCS "main.cc"
         "logic/irrigation.cc" "logic/species.cc" "logic/species_profiles.cc" "logic/preprocess.cc"
         "hw/classifier.cc" "hw/camera.cc" "hw/sensors.cc" "hw/actuators.cc" "hw/telemetry.cc"
         "generated/model_data.cc" "generated/golden_data.cc"
    INCLUDE_DIRS "." "logic" "hw" "generated")

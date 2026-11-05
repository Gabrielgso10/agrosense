import numpy as np
import tensorflow as tf

from evaluation import max_abs_diff_lsb, op_names_in_model, pick_golden_index


def test_golden_is_first_sample_where_all_interpreters_agree_and_are_right():
    y_true = np.array([0, 1, 2, 1])
    float_pred = np.array([1, 1, 2, 1])
    litert_pred = np.array([0, 1, 0, 1])
    tflm_pred = np.array([0, 1, 2, 1])
    assert pick_golden_index(y_true, float_pred, litert_pred, tflm_pred) == 1


def test_golden_falls_back_to_first_sample_when_nobody_agrees():
    y = np.array([0, 1])
    assert pick_golden_index(y, np.array([1, 0]), np.array([1, 0]), np.array([1, 0])) == 0


def test_lsb_difference_is_computed_without_int8_overflow():
    a = np.array([[127, -128]], dtype=np.int8)
    b = np.array([[-128, 127]], dtype=np.int8)
    assert max_abs_diff_lsb(a, b) == 255


def test_op_names_are_read_from_a_real_converted_model():
    model = tf.keras.Sequential([tf.keras.Input((4,)), tf.keras.layers.Dense(3, activation="softmax")])
    tflite_bytes = tf.lite.TFLiteConverter.from_keras_model(model).convert()
    names = op_names_in_model(tflite_bytes)
    assert "FULLY_CONNECTED" in names and "SOFTMAX" in names

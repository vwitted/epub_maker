import os
from unittest.mock import MagicMock, patch
import sys

# Add current dir to path to import convert
sys.path.append(os.getcwd())
import convert

def test_optimization_logic():
    print("Testing CPU-only scenario...")
    with patch('torch.cuda.is_available', return_value=False):
        with patch('os.cpu_count', return_value=8):
            workers, batch_size = convert.get_hardware_config()
            print(f"CPU (8 cores) -> workers: {workers}, batch_size: {batch_size}")
            assert workers == 8
            assert batch_size == 1

    print("\nTesting GPU (low VRAM) scenario...")
    mock_props = MagicMock()
    mock_props.total_memory = 8 * (1024**3) # 8GB
    with patch('torch.cuda.is_available', return_value=True):
        with patch('torch.cuda.device_count', return_value=1):
            with patch('torch.cuda.get_device_properties', return_value=mock_props):
                workers, batch_size = convert.get_hardware_config()
                print(f"GPU (8GB VRAM) -> workers: {workers}, batch_size: {batch_size}")
                assert workers == 1
                assert batch_size == 8

    print("\nTesting GPU (high VRAM) scenario...")
    mock_props_high = MagicMock()
    mock_props_high.total_memory = 24 * (1024**3) # 24GB
    with patch('torch.cuda.is_available', return_value=True):
        with patch('torch.cuda.device_count', return_value=1):
            with patch('torch.cuda.get_device_properties', return_value=mock_props_high):
                workers, batch_size = convert.get_hardware_config()
                print(f"GPU (24GB VRAM) -> workers: {workers}, batch_size: {batch_size}")
                assert workers == 4 # 24 // 5 = 4
                assert batch_size == 8

    print("\nALL LOGIC TESTS PASSED.")

if __name__ == "__main__":
    try:
        test_optimization_logic()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()

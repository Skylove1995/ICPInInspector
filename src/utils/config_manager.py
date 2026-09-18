import json
import os

class ConfigManager:
    def __init__(self, config_path="config/config.json"):
        self.config_path = config_path

    def load_config(self):
        if not os.path.exists(self.config_path):
            return self._default_config()
        with open(self.config_path, "r") as f:
            try:
                data = json.load(f)
                # Ensure default keys exist
                defaults = self._default_config()
                for k, v in defaults.items():
                    if k not in data:
                        data[k] = v
                return data
            except json.JSONDecodeError:
                return self._default_config()

    def save_config(self, config):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=4)
        print(f"Config saved to {self.config_path}")

    def load_rois(self):
        config = self.load_config()
        return config.get("rois", [])

    def save_rois(self, rois):
        config = self.load_config()
        config["rois"] = rois
        self.save_config(config)

    def _default_config(self):
        return {
            "num_rois": 4,
            "rois": [],
            "preprocessing": {
                "blur_kernel": 5,
                "threshold_block_size": 21,
                "threshold_c": 10,
                "morph_kernel": 3,
                "debug_mode": True
            }
        }

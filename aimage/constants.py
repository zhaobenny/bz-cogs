
DEFAULT_NEGATIVE_PROMPT = "ugly, tiling, poorly drawn hands, poorly drawn feet, poorly drawn face, out of frame, extra limbs, disfigured, deformed, body out of frame, bad anatomy, watermark, signature, cut off, low contrast, underexposed, overexposed, bad art, beginner, amateur, distorted face"

# taken from https://www.greataiprompts.com/imageprompt/list-of-banned-words-in-midjourney/
DEFAULT_BADWORDS_BLACKLIST = ["blood", "bloodbath", "crucifixion", "bloody", "flesh", "bruises", "car crash", "corpse", "crucified", "cutting", "decapitate", "infested", "gruesome", "kill", "infected", "sadist", "slaughter", "teratoma", "tryphophobia", "wound", "cronenberg", "khorne", "cannibal", "cannibalism", "visceral", "guts", "bloodshot", "gory", "killing", "surgery", "vivisection", "massacre", "hemoglobin", "suicide", "female body parts", "ahegao", "pinup", "ballgag", "playboy", "bimbo", "pleasure", "bodily fluids", "pleasures", "boudoir", "rule34", "brothel", "seducing", "dominatrix", "seductive", "erotic seductive", "fuck", "sensual", "hardcore", "sexy", "hentai", "shag", "horny", "shibari", "incest", "smut", "jav", "succubus", "jerk off king at pic", "thot", "kinbaku", "transparent", "legs spread", "twerk", "making love", "voluptuous", "naughty", "wincest", "orgy", "sultry",
                              "xxx", "bondage", "bdsm", "dog collar", "slavegirl", "transparent and translucent", "arse", "labia", "ass", "mammaries", "human centipede", "badonkers", "minge", "massive chests", "big ass", "mommy milker", "booba", "nipple", "booty", "oppai", "bosom", "organs", "breasts", "ovaries", "busty", "penis", "clunge", "phallus", "crotch", "sexy female", "dick", "skimpy", "girth", "thick", "honkers", "vagina", "hooters", "veiny", "knob", "no clothes", "speedo", "au naturale", "no shirt", "bare chest", "nude", "barely dressed", "bra", "risqué", "clear", "scantily clad", "cleavage", "stripped", "full frontal unclothed", "invisible clothes", "wearing nothing", "lingerie with no shirt", "naked", "without clothes on", "negligee", "zero clothes", "taboo", "fascist", "nazi", "prophet mohammed", "slave", "coon", "honkey", "arrested", "jail", "handcuffs", "drugs", "cocaine", "heroin", "meth", "crack"]

VIEW_TIMEOUT = 180

AUTO_COMPLETE_SAMPLERS = [
    "DPM++ 2M Karras",
    "DPM++ SDE Karras",
    "DPM++ 2M SDE Exponential",
    "DPM++ 2M SDE Karras",
    "Euler a",
    "Euler",
    "LMS",
    "Heun",
    "DPM2",
    "DPM2 a",
    "DPM++ 2S a",
    "DPM++ 2M",
    "DPM++ SDE",
    "DPM++ 2M SDE",
    "DPM++ 2M SDE Heun",
    "DPM++ 2M SDE Heun Karras",
    "DPM++ 2M SDE Heun Exponential",
    "DPM++ 3M SDE",
    "DPM++ 3M SDE Karras",
    "DPM++ 3M SDE Exponential",
    "DPM fast",
    "DPM adaptive",
    "LMS Karras",
    "DPM2 Karras",
    "DPM2 a Karras",
    "DPM++ 2S a Karras",
    "Restart",
    "DDIM",
    "PLMS",
    "UniPC"
]

ADETAILER_ARGS = {
    "ADetailer": {
        "args": [
            True,
            False,
            {
                "ad_model": "face_yolov8n.pt",
                "ad_prompt": "",
                "ad_negative_prompt": "",
                "ad_confidence": 0.3,
                "ad_mask_k_largest": 0,
                "ad_mask_min_ratio": 0.0,
                "ad_mask_max_ratio": 1.0,
                "ad_dilate_erode": 32,
                "ad_x_offset": 0,
                "ad_y_offset": 0,
                "ad_mask_merge_invert": "None",
                "ad_mask_blur": 4,
                "ad_denoising_strength": 0.4,
                "ad_inpaint_only_masked": True,
                "ad_inpaint_only_masked_padding": 0,
                "ad_use_inpaint_width_height": False,
                "ad_inpaint_width": 512,
                "ad_inpaint_height": 512,
                "ad_use_steps": True,
                "ad_steps": 28,
                "ad_use_cfg_scale": False,
                "ad_cfg_scale": 7.0,
                "ad_use_sampler": False,
                "ad_sampler": "DPM++ 2M Karras",
                "ad_use_noise_multiplier": False,
                "ad_noise_multiplier": 1.0,
                "ad_use_clip_skip": False,
                "ad_clip_skip": 1,
                "ad_restore_face": False,
                "ad_controlnet_model": "None",
                "ad_controlnet_module": "None",
                "ad_controlnet_weight": 1.0,
                "ad_controlnet_guidance_start": 0.0,
                "ad_controlnet_guidance_end": 1.0
            }
        ]
    }
}

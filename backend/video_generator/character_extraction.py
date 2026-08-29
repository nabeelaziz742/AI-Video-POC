import re


def extract_characters_from_story(prompt: str) -> list[dict]:
    """
    Intelligently extracts a coherent main character from a user's story or script prompt.
    Provides rich default attributes for character continuity without requiring manual user configuration.
    """
    cleaned_prompt = (prompt or "").strip()
    lower_prompt = cleaned_prompt.lower()

    # Pattern match common archetypes / character identifiers in the prompt
    archetypes = [
        ("young explorer", "Young Explorer", "young adventurer in their early 20s", "curious face, energetic posture, bright eyes", "futuristic travel jacket with durable utility pants and boots", "brave, inquisitive, and adventurous"),
        ("explorer", "Explorer", "adventurer in their 20s", "determined expression, keen eyes", "weathered explorer jacket with utility belt and sturdy boots", "resourceful, curious, and daring"),
        ("farmer", "Farmer", "adult in their 40s", "warm friendly face, kind eyes, sturdy build", "traditional earthy working tunic with vest and sturdy boots", "hardworking, humble, and warm-hearted"),
        ("detective", "Detective", "adult in their 30s", "sharp observant eyes, focused posture", "classic trench coat with tailored collar", "analytical, observant, and calm"),
        ("astronaut", "Astronaut", "adult in their 30s", "athletic build, confident focused expression", "sleek modern spacesuit with subtle luminescent accents", "courageous, disciplined, and visionary"),
        ("scientist", "Scientist", "adult in their 30s", "intelligent expressive face, thoughtful gaze", "modern lab coat over casual tech apparel", "brilliant, methodical, and passionate"),
        ("warrior", "Warrior", "adult in their 20s-30s", "strong athletic build, focused gaze", "light battle-ready armor with leather accents", "honorable, determined, and courageous"),
        ("robot", "Cyber Companion", "advanced robotic entity", "sleek metallic chassis with glowing cyan optical sensors", "brushed titanium plating with smooth articulation joints", "helpful, precise, and loyal"),
        ("girl", "Young Heroine", "young girl in her teens", "spirited expressive face, bright eyes", "comfortable modern casual clothing with colorful jacket", "creative, kind, and brave"),
        ("boy", "Young Hero", "young boy in his teens", "cheerful animated face, lively eyes", "casual hoodie with denim trousers and sneakers", "playful, daring, and loyal"),
        ("traveler", "Traveler", "adult in their 20s-30s", "weathered friendly features, observant gaze", "layered traveler cloak and durable field attire", "open-minded, adaptable, and observant"),
        ("wizard", "Mage", "wise adult", "mysterious expressive eyes, serene presence", "flowing embroidered robes with celestial patterns", "wise, enigmatic, and powerful"),
        ("pilot", "Pilot", "adult in their 20s-30s", "confident smile, alert gaze", "flight jacket with aviator badges and tactical gloves", "fearless, skilled, and quick-thinking"),
    ]

    selected_name = "Protagonist"
    selected_age = "young adult in their 20s"
    selected_appearance = "distinctive friendly face, expressive eyes, well-proportioned features"
    selected_clothing = "modern stylish apparel suited for their adventure"
    selected_personality = "curious, determined, and expressive"

    for keyword, name, age, appearance, clothing, personality in archetypes:
        if re.search(r"\b" + re.escape(keyword) + r"\b", lower_prompt):
            selected_name = name
            selected_age = age
            selected_appearance = appearance
            selected_clothing = clothing
            selected_personality = personality
            break

    # Contextual environment adjustments
    if "futuristic" in lower_prompt or "cyber" in lower_prompt or "sci-fi" in lower_prompt:
        if "futuristic" not in selected_clothing:
            selected_clothing = "futuristic sci-fi attire with subtle glowing accents and travel gear"
    elif "fantasy" in lower_prompt or "magic" in lower_prompt or "castle" in lower_prompt:
        selected_clothing = "finely woven fantasy garments with leather belts and boots"

    visual_prompt = (
        "polished 3D animated character, Pixar and DreamWorks inspired aesthetic, "
        "cinematic rim lighting, rich surface textures, centered character framing, neutral studio background"
    )

    character_dict = {
        "name": selected_name,
        "role": "main character",
        "age_description": selected_age,
        "appearance": selected_appearance,
        "clothing": selected_clothing,
        "personality": selected_personality,
        "description": f"The main character in the story: {cleaned_prompt[:120]}",
        "visual_prompt": visual_prompt,
    }

    return [character_dict]

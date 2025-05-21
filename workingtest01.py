import re
import json
import random
import requests
import base64
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Initialize Gemini client
client = genai.Client(api_key="AIzaSyDpaOZq0jE6d4SdTpf1GyNk_lLkB75Kn_8")

# --- SEARCH TOOLS ---

def search_links(query, max_results=8):
    """Enhanced search function that gets more detailed results"""
    results = []
    
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results+3))
            
            # Filter out low-quality results
            for r in raw_results:
                # Skip results with very short snippets or missing information
                if not r.get("body") or len(r.get("body", "")) < 30:
                    continue
                
                domain = urlparse(r["href"]).netloc
                # Skip some common problematic domains
                if any(x in domain for x in ['pinterest', 'facebook.com', 'instagram.com']):
                    continue
                    
                results.append({
                    "title": r["title"],
                    "link": r["href"],
                    "snippet": r.get("body", ""),
                    "domain": domain
                })
                
                if len(results) >= max_results:
                    break
                    
    except Exception as e:
        print(f"Search error: {e}")
        # Provide at least some fallback results
        results = [{
            "title": f"Resource about {query}",
            "link": f"https://www.example.com/resource-{random.randint(1, 100)}",
            "snippet": f"Information related to {query} and its applications.",
            "domain": "example.com"
        }]
        
    return results

def get_content_preview(url, timeout=5):
    """Get a preview of content from a URL to provide better context to AI"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=timeout)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.extract()
                
            # Get main content - look for common content containers
            content_tags = soup.select('article, .content, .post, .entry, .main, main, #content, #main')
            
            if content_tags:
                main_content = content_tags[0].get_text(strip=True)
            else:
                # Fallback to body text
                main_content = soup.body.get_text(strip=True) if soup.body else ""
                
            # Clean and truncate content
            content = re.sub(r'\s+', ' ', main_content).strip()
            if len(content) > 1000:
                content = content[:997] + "..."
                
            # Extract meta description for additional context
            meta_desc = ""
            meta_tag = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if meta_tag and 'content' in meta_tag.attrs:
                meta_desc = meta_tag['content']
                
            return {
                "title": soup.title.string if soup.title else "",
                "meta_description": meta_desc,
                "excerpt": content
            }
            
    except Exception as e:
        print(f"Error fetching content from {url}: {e}")
    
    return {
        "title": "",
        "meta_description": "",
        "excerpt": f"[Content preview unavailable for {url}]"
    }

# --- IMAGE GENERATION ---

def generate_image(prompt, output_file=None):
    """Generate an image using Gemini API based on the prompt"""
    print(f"🎨 Generating image: {prompt[:50]}...")
    
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash-preview-image-generation",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE']
            )
        )
        
        # Process and save image
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                image = Image.open(BytesIO((part.inline_data.data)))
                
                # Save image if filename provided
                if output_file:
                    image.save(output_file)
                    print(f"Image saved as {output_file}")
                
                # Convert to base64 for embedding in HTML
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                return {
                    "base64": img_str,
                    "alt_text": prompt[:60] + "..."
                }
    
    except Exception as e:
        print(f"Error generating image: {e}")
    
    return None

def generate_blog_images(topic, image_count=3):
    """Generate a set of blog images based on topic"""
    # Revised prompt list to generate visually strong and safe blog images
    image_prompts = [
        f"Create a professional featured image for a blog post about '{topic}'. Use bold colors, depth, and clean design with no text.",
        f"Create a futuristic and conceptual illustration representing the idea of '{topic}'.",
        f"Generate a symbolic visual that captures the essence or core meaning of '{topic}' — use abstract design."
    ]

    additional_prompts = [
        f"Design an artistic header image that visually represents '{topic}' in a modern or tech-inspired style.",
        f"Create a minimal and elegant illustration using objects or metaphors related to '{topic}' (e.g., brain, cloud, circuits, robot).",
        f"Produce a creative, clean image that symbolizes innovation or advancement in the context of '{topic}'."
    ]

      # Combine and shuffle prompts
    needed_additional = max(0, min(image_count - len(image_prompts), len(additional_prompts)))
    all_prompts = image_prompts + random.sample(additional_prompts, needed_additional) if needed_additional > 0 else image_prompts
    selected_prompts = random.sample(all_prompts, min(image_count, len(all_prompts)))
    
    images = []
    for i, prompt in enumerate(selected_prompts):
        image_file = f"blog_image_{i+1}.png"
        image_data = generate_image(prompt, image_file)
        if image_data:
            images.append({
                "file": image_file,
                "base64": image_data["base64"],
                "alt_text": image_data["alt_text"],
                "caption": f"Image {i+1}: {topic}-related visual"
            })
    
    return images

# --- PROMPTS ---

BLOG_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{meta_description}">
  <title>{page_title}</title>  <style>
    /* Reset and Base styles */
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    
    body {{
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      line-height: 1.6;
      color: #333;
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 15px;
    }}
    
    /* Header styles */
    header {{
      padding: 20px 0;
      border-bottom: 1px solid #eaeaea;
      margin-bottom: 30px;
    }}
    
    .site-title {{
      font-size: 24px;
      font-weight: bold;
      margin: 0;
      padding: 0;
    }}
    
    nav {{
      display: flex;
      flex-wrap: wrap;
      margin-top: 15px;
    }}
    
    nav a {{
      margin-right: 20px;
      color: #555;
      text-decoration: none;
      padding: 5px 0;
    }}
    
    nav a:hover {{
      color: #1a73e8;
    }}
    
    /* Content styles */
    .post-meta {{
      color: #777;
      font-size: 0.9em;
      margin-bottom: 25px;
    }}
    
    h1 {{
      font-size: 32px;
      line-height: 1.2;
      margin-bottom: 15px;
      color: #222;
    }}
    
    h2 {{
      font-size: 24px;
      margin-top: 40px;
      margin-bottom: 15px;
      color: #333;
    }}
    
    h3 {{
      font-size: 20px;
      margin-top: 30px;
      margin-bottom: 10px;
    }}
    
    p {{
      margin-bottom: 20px;
    }}
    
    img {{
      max-width: 100%;
      height: auto;
      margin: 25px 0;
      border-radius: 5px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }}
    
    .image-caption {{
      text-align: center;
      font-size: 0.9em;
      color: #666;
      margin-top: -20px;
      margin-bottom: 30px;
    }}
    
    ul, ol {{
      margin-bottom: 25px;
      padding-left: 25px;
    }}
    
    li {{
      margin-bottom: 8px;
    }}
    
    blockquote {{
      border-left: 4px solid #1a73e8;
      padding: 10px 20px;
      margin: 20px 0;
      background-color: #f8f9fa;
      font-style: italic;
    }}
    
    /* Footer styles */
    footer {{
      margin-top: 50px;
      padding: 20px 0;
      border-top: 1px solid #eaeaea;
      text-align: center;
      font-size: 0.9em;
      color: #777;
    }}
    
    .back-to-top {{
      display: inline-block;
      margin-top: 10px;
      font-size: 0.8em;
      color: #1a73e8;
      text-decoration: none;
    }}
    
    /* Responsive fixes */
    @media (max-width: 768px) {{
      nav {{
        flex-direction: column;
      }}
      
      nav a {{
        margin-bottom: 5px;
      }}
    }}
  </style>
</head>
<body>  <a href="#main-content" class="skip-link">Skip to content</a>
  <div class="container">
    <header>
      <div class="header-content">
        <h1 class="site-title"><a href="https://craftingcurrents.blogspot.com/">Crafting Currents</a></h1>
      </div>
      <nav>
        <a href="https://craftingcurrents.blogspot.com/">Home</a>
        <a href="https://craftingcurrents.blogspot.com/p/about-us.html">About Us</a>
        <a href="https://craftingcurrents.blogspot.com/p/contact-us.html">Contact Us</a>
      </nav>
    </header>

    <main id="main-content">
      <article>
        <h1>{blog_title}</h1>
        <div class="post-meta">
          <span>Published: {publish_date}</span>
          <span>Category: <a href="https://craftingcurrents.blogspot.com/search/label/{category}">{category}</a></span>
        </div>
      
      <!-- CONTENT_PLACEHOLDER -->
      
    </article>
  </main>
  
  <footer>
    <div>© {current_year} My Professional Blog. All Rights Reserved.</div>
    <a href="#" class="back-to-top">Back to Top</a>
    <a href="https://craftingcurrents.blogspot.com/p/disclaimer.html">Disclaimer</a>
    <a href="https://craftingcurrents.blogspot.com/p/privacy-policy.html">Privacy Policy</a>
  </footer>
</body>
</html>
'''

BLOG_CONTENT_PROMPT = """
You are tasked with creating a Wikipedia-style blog post about **{topic}**. The goal is to provide a well-structured, factual, and comprehensive article that is neutral in tone and highly informative.

🎯 OBJECTIVE:
Create a blog post that is clear, concise, and focused on delivering quality information. Avoid personal opinions, conversational tone, or unnecessary embellishments. The content should be structured and easy to navigate, similar to a Wikipedia article.

🧱 STRUCTURE GUIDANCE:
- **Introduction**: Provide a brief overview of the topic, including its significance and context.
- **Main Sections** (`<h2>`): Organize the content into logical sections with descriptive headings.
- **Subsections** (`<h3>`): Use subsections to break down complex topics.
- **Data & References**: Include at least 3 unique references from the {search_data} and {resource_previews}.
- **Conclusion**: Summarize the key points and provide any additional insights or related information.

🎨 FORMATTING RULES:
- Use proper HTML structure
- Use `<h2>` for main sections, `<h3>` for subsections
- Use `<strong>` and `<em>` sparingly for emphasis
- Use `<ul>`/`<ol>` for lists where appropriate
- Use `<blockquote>` for important quotes or data
- Leave appropriate spacing
- Include `{image_placeholders}` where visuals would enhance understanding
- Insert `<!-- AdSense Code Here -->` in 2-3 natural places for ad placement

🔒 FINAL OUTPUT MUST:
- Be neutral, factual, and well-researched
- Use the provided {search_data} and {resource_previews} with clear attribution
- Follow a structured and professional format
"""

HUMANIZE_PROMPT = """
You are a skilled content editor tasked with improving the clarity, neutrality, and factual accuracy of the following blog content. Your goal is to:

📌 GOALS:
- Ensure the content is neutral, objective, and free of bias.
- Improve readability and logical flow.
- Maintain a professional and structured tone.

✅ EDITING GUIDELINES:
1. Use concise and clear language.
2. Avoid conversational phrases or emotional language.
3. Ensure all claims are factual and well-supported.
4. Structure the content with proper headings and subheadings.
5. Eliminate redundancy and overly complex sentences.

📄 FINAL OUTPUT:
Return the revised content in a neutral, professional tone suitable for an informational blog or article.
"""

GRAMMAR_REWRITE_PROMPT = """
You are a professional proofreader. Your task is to:

📌 GOALS:
- Correct grammatical errors and improve sentence structure.
- Ensure clarity and conciseness.
- Maintain a neutral and professional tone.

✅ EDITING GUIDELINES:
1. Fix any grammatical, punctuation, or spelling errors.
2. Simplify overly complex sentences while preserving meaning.
3. Ensure logical flow and coherence between paragraphs.
4. Avoid adding any subjective opinions or conversational elements.

📄 FINAL OUTPUT:
Return the revised content with improved grammar and clarity, suitable for a factual and structured blog post.
"""

# --- UTILITY FUNCTIONS ---

def extract_content(content):
    match = re.search(r"```(?:html)?(.*?)```", content, re.DOTALL)
    return match.group(1).strip() if match else content.strip()

def write_to_file(filename, content):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

def generate(prompt, temperature=0.9):
    """Generate content with variable temperature to increase randomness"""
    return client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    ).text

def get_enriched_search_data(topic):
    """Get comprehensive search data with content previews"""
    print(f"🔍 Searching for resources on: {topic}")
    
    # Start with base search
    search_results = search_links(topic, max_results=6)
    
    # Get related topics for additional context
    related_topics = [
        f"{topic} examples", 
        f"{topic} tutorial", 
        f"{topic} vs", 
        f"how to use {topic}", 
        f"{topic} benefits"
    ]
    
    # Add 1-2 results from related searches
    for related in random.sample(related_topics, 2):
        extra_results = search_links(related, max_results=2)
        if extra_results:
            search_results.extend(extra_results[:1])
    
    # Get content previews for a few top results
    print("📄 Fetching content previews from search results...")
    resource_previews = []
    
    for i, result in enumerate(search_results[:4]):
        print(f"  - Getting preview for {result['title'][:40]}...")
        preview = get_content_preview(result['link'])
        if preview and preview['excerpt'] and len(preview['excerpt']) > 100:
            resource_previews.append({
                "title": result['title'],
                "link": result['link'],
                "preview": preview['excerpt'][:800]  # Limit preview length
            })
    
    return {
        "search_results": search_results,
        "resource_previews": resource_previews
    }

def generate_image_placeholders(count=3):
    """Generate placeholder strings for images to be inserted in content"""
    placeholders = []
    for i in range(count):
        placeholders.append(f"[IMAGE_PLACEHOLDER_{i+1}]")
    return placeholders

def replace_image_placeholders(content, images):
    """Replace image placeholders with actual image tags using base64 data"""
    result = content
    for i, image in enumerate(images):
        placeholder = f"[IMAGE_PLACEHOLDER_{i+1}]"
        img_tag = f"""
        <figure>
          <img src="data:image/png;base64,{image['base64']}" alt="{image['alt_text']}" />
          <figcaption class="image-caption">{image['caption']}</figcaption>
        </figure>
        """
        result = result.replace(placeholder, img_tag)
    
    # Replace any remaining placeholders
    for i in range(len(images) + 1, 10):
        placeholder = f"[IMAGE_PLACEHOLDER_{i}]"
        if placeholder in result:
            result = result.replace(placeholder, "<!-- Image placeholder not filled -->")
    
    return result

# --- MAIN PROCESS ---

def generate_blogger_content(topic, image_count=3):
    """Generate human-like blog content ready for Blogger with images"""
    import datetime
    
    # Get comprehensive search data
    enriched_data = get_enriched_search_data(topic)
    search_results = enriched_data["search_results"]
    resource_previews = enriched_data["resource_previews"]
    
    # Prepare data for prompt
    search_data_json = json.dumps(search_results, indent=2)
    resource_previews_json = json.dumps(resource_previews, indent=2)
    
    # Generate image placeholders
    image_placeholders = generate_image_placeholders(image_count)
    placeholders_str = ", ".join(image_placeholders)
    
    print("✍️ Step 1: Generating initial blog draft...")
    blog_prompt = BLOG_CONTENT_PROMPT.format(
        topic=topic, 
        search_data=search_data_json,
        resource_previews=resource_previews_json,
        image_placeholders=placeholders_str
    )
      # Use higher temperature for more randomness/creativity
    blog_content_raw = extract_content(generate(blog_prompt, temperature=0.9))
    write_to_file("step1_draft.html", blog_content_raw)
    
    print("🧠 Step 2: Applying deep humanization...")
    # Higher temperature for unpredictable human-like variations
    blog_content_human = extract_content(generate(HUMANIZE_PROMPT + "\n\n" + blog_content_raw, temperature=1.0))
    write_to_file("step2_humanized.html", blog_content_human)
    
    print("✍️ Step 3: Polishing grammar and cleaning up formatting...")
    # Use slightly lower temperature for more controlled grammar improvements
    blog_content_polished = extract_content(generate(GRAMMAR_REWRITE_PROMPT + "\n\n" + blog_content_human, temperature=0.7))
    write_to_file("step3_polished.html", blog_content_polished)
    
    print("🎨 Step 4: Generating blog images...")
    blog_images = generate_blog_images(topic, image_count)
    
    print("🔄 Step 5: Replacing image placeholders with generated images...")
    blog_content_with_images = replace_image_placeholders(blog_content_polished, blog_images)
    
    # Generate SEO elements
    seo_prompt = f"""Create SEO elements for a blog post about {topic}:
    1. An engaging title (under 60 characters)
    2. A compelling meta description (under 155 characters)
    3. A relevant category for the blog post
    
    Make these sound completely natural and human-written.
    Format as: Title: [your title]\\nDescription: [your description]\\nCategory: [category]
    """
    
    seo_elements = generate(seo_prompt, temperature=0.8).strip()
    
    try:
        title_match = re.search(r"Title:(.*?)(?:\n|$)", seo_elements)
        desc_match = re.search(r"Description:(.*?)(?:\n|$)", seo_elements)
        cat_match = re.search(r"Category:(.*?)(?:\n|$)", seo_elements)
        
        blog_title = title_match.group(1).strip() if title_match else f"{topic} - A Complete Guide"
        meta_description = desc_match.group(1).strip() if desc_match else f"Learn everything about {topic} in this comprehensive guide."
        category = cat_match.group(1).strip() if cat_match else "General"
        
        # Current date for publishing
        publish_date = datetime.datetime.now().strftime("%B %d, %Y")
        current_year = datetime.datetime.now().year
        
        print("\n📝 Generated SEO Elements:")
        print(f"Title: {blog_title}")
        print(f"Description: {meta_description}")
        print(f"Category: {category}")
        
        # Save SEO elements to a separate file
        with open("blogger_seo.txt", "w", encoding="utf-8") as f:
            f.write(f"Title: {blog_title}\nDescription: {meta_description}\nCategory: {category}")
            
    except Exception as e:
        print(f"Error parsing SEO elements: {e}")
        blog_title = f"{topic} - A Complete Guide"
        meta_description = f"Learn everything about {topic} in this comprehensive guide."
        category = "General"
        publish_date = datetime.datetime.now().strftime("%B %d, %Y")
        current_year = datetime.datetime.now().year
    
    # Construct the full blog HTML with our template
    blog_template = BLOG_TEMPLATE.format(
        blog_title=blog_title,
        page_title=blog_title,
        meta_description=meta_description,
        category=category,
        publish_date=publish_date,
        current_year=current_year
    )
    
    # Insert the blog content into the template
    full_blog_html = blog_template.replace("<!-- CONTENT_PLACEHOLDER -->", blog_content_with_images)
    
    # Write the final blog HTML to file
    write_to_file("blogger_final.html", full_blog_html)
    
    print("\n🚀 Final blog content saved as 'blogger_final.html' (ready for Blogger)")
    print("💡 SEO elements saved in 'blogger_seo.txt'")
    print(f"🖼️ Generated {len(blog_images)} images for the blog")

# --- EXECUTION ---

if __name__ == "__main__":
    topic = input("Enter blog topic: ").strip() or "Google GenAI"
    image_count = int(input("How many images to generate (1-5)? ") or "3")
    image_count = max(1, min(5, image_count))  # Limit between 1-5
    generate_blogger_content(topic, image_count)
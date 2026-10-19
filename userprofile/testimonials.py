"""Veteran testimonials shown on the public site.

`topic` is "bootcamp" or "career". The homepage features boot camp quotes
first, since the coding boot camp is the main program.
"""

BOOTCAMP = "bootcamp"
CAREER = "career"

TESTIMONIALS = [
    {
        "quote": "This course was perfect as an introduction into coding and web dev, and not intimidating at all. "
        "I would highly recommend it to others.",
        "name": "Ariel Taylor",
        "branch": "US Navy Veteran",
        "topic": BOOTCAMP,
    },
    {
        "quote": "I wanted to have coding demystified, and it did just that.",
        "name": "Marnie Tait",
        "branch": "US Army Veteran",
        "topic": BOOTCAMP,
    },
    {
        "quote": "The resume writing and tailoring were extremely helpful, as well as the job search guidance and "
        "feedback. I believe these all contributed most to me finding a job.",
        "name": "Kyle Vandenbrandhorninge",
        "branch": "US Marine Corps Veteran",
        "topic": CAREER,
    },
    {
        "quote": "Excellent intro to coding with well-supported materials and a knowledgeable instructor who was "
        "well-attuned to the needs of a wide range of students and abilities.",
        "name": "Greg O'Shea",
        "branch": "US Navy Veteran",
        "topic": BOOTCAMP,
    },
    {
        "quote": "The team was very knowledgeable and helpful. I was able to learn a new skill that I can further "
        "develop.",
        "name": "Emilio Herrera",
        "branch": "US Air Force Veteran",
        "topic": BOOTCAMP,
    },
    {
        "quote": "It is a rare thing in this world to find an organization or a person who will do something for "
        "another person with no expectations. Hired Labs is one of these rare chances to get a boost and a bit "
        "of assistance to making a change in your life happen.",
        "name": "Chris Schrachta",
        "branch": "US Navy Veteran",
        "topic": BOOTCAMP,
    },
    {
        "quote": "The example web app is a simple and achievable goal and everything is explained and reviewed.",
        "name": "Chris Schrachta",
        "branch": "US Navy Veteran",
        "topic": BOOTCAMP,
    },
    {
        "quote": "I think the format was excellent for a novice like myself.",
        "name": "Marnie Tait",
        "branch": "US Army Veteran",
        "topic": BOOTCAMP,
    },
    {
        "quote": "Communication was a real bonus, on the calls and via Discord and email. Recording the sessions "
        "was great too.",
        "name": "Marnie Tait",
        "branch": "US Army Veteran",
        "topic": BOOTCAMP,
    },
    {
        "quote": "Your team's dedication and sincere effort in partnering with me throughout the journey of "
        "securing a new job have made a significant impact on my career transition.",
        "name": "Eddie Lemus",
        "branch": "US Marine Corps Veteran",
        "topic": CAREER,
    },
    {
        "quote": "Weekly tailored jobs helped organize all jobs that I applied to, and having a job sourced on my "
        "behalf was invaluable.",
        "name": "Eddie Lemus",
        "branch": "US Marine Corps Veteran",
        "topic": CAREER,
    },
    {
        "quote": "I had a great time with everyone on the team. Everyone is eager to help and extremely "
        "knowledgeable about the current job market and hiring trends.",
        "name": "Kyle Vandenbrandhorninge",
        "branch": "US Marine Corps Veteran",
        "topic": CAREER,
    },
    {
        "quote": "It was just a big help not having to spend a ton of time editing my resume myself.",
        "name": "Chad Fosse",
        "branch": "US Marine Corps Veteran",
        "topic": CAREER,
    },
    {
        "quote": "Veterans helping veterans always motivates me.",
        "name": "Kyle Vandenbrandhorninge",
        "branch": "US Marine Corps Veteran",
        "topic": CAREER,
    },
]

# Homepage cards: two boot camp quotes, then one career quote.
HOMEPAGE = [TESTIMONIALS[0], TESTIMONIALS[1], TESTIMONIALS[2]]

# Pull quote on the Services page, under the boot camp section.
SERVICES_FEATURE = TESTIMONIALS[3]

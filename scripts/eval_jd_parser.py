from __future__ import annotations

from ats_matcher.jd_parser import JDParser


EXAMPLE_JDS = [
    "We need experience in enterprise performance area, financial planning, and SQL.",
    "Minimum 5 years of working experience. Strong machine learning and AWS preferred.",
    "Own stakeholder communication, product analytics, and BI dashboard development.",
]


def main() -> None:
    parser = JDParser()

    for idx, jd_text in enumerate(EXAMPLE_JDS, start=1):
        components = parser.extract_skill_components(jd_text)
        combined = parser.extract_skill_terms(jd_text)

        print(f"\n=== JD #{idx} ===")
        print(jd_text)
        print("- ESCO skills:")
        for item in components["esco_skills"]:
            print(f"  - {item}")
        print("- Clean noun-chunk skills:")
        for item in components["noun_chunk_skills"]:
            print(f"  - {item}")
        print("- Combined candidates:")
        for item in combined:
            print(f"  - {item}")


if __name__ == "__main__":
    main()

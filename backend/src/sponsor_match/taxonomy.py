"""Bootstrap concepts are explicitly local, never mislabelled as ESCO/SOC."""
import re
from dataclasses import dataclass, asdict, field
from .models import Profile, RoleIntent


def key(value: str) -> str:
    return re.sub(r"[^\w]+", " ", value.casefold()).strip()


def contains(text: str, phrase: str) -> bool:
    normalized=key(phrase)
    if not normalized:
        return False
    # Common singular/plural role labels are equivalent, not career alternatives.
    variants=[normalized,normalized+"s"]
    if normalized.endswith("y"):
        variants.append(normalized[:-1]+"ies")
    return any(f" {v} " in f" {key(text)} " for v in variants)


@dataclass
class Concept:
    id: str
    label: str
    aliases: list[str]
    activities: list[str]
    skills: list[str]
    backgrounds: list[str]
    related: list[str]
    version: str = "bootstrap-2"
    kind: str = "occupation"
    metadata: dict = field(default_factory=dict)


# Activity phrases describe delivery of professional work. Generic sectors and
# universal corporate-function assumptions are intentionally absent.
SEEDS = [
 ("mechanical", "Mechanical engineer", ["mechanical engineering", "mechanical design engineer", "mechanical designer", "production engineer", "manufacturing engineer"], ["mechanical design", "precision engineering", "manufacturing engineering", "automotive engineering"], ["cad", "solidworks", "manufacturing", "thermodynamics"], ["mechanical engineering"], ["technical_sales", "project_management"]),
 ("electrical", "Electrical engineer", ["electrical engineering", "electrical design engineer", "electronics engineer"], ["electrical design", "electronics design", "electrical engineering"], ["circuits", "pcb", "electrical systems"], ["electrical engineering", "electronics"], ["mechanical"]),
 ("civil", "Civil engineer", ["civil engineering", "structural engineer"], ["structural engineering", "civil engineering", "geotechnical design"], ["structural analysis", "autocad", "infrastructure"], ["civil engineering"], ["project_management"]),
 ("software", "Software developer", ["software engineer", "programmer", "web developer", "full stack developer"], ["software development", "application development", "web development"], ["python", "javascript", "typescript", "programming"], ["computer science", "software engineering"], ["data"]),
 ("data", "Data analyst", ["data analytics", "business intelligence analyst", "data scientist"], ["data analytics", "business intelligence services", "data science"], ["sql", "statistics", "python", "power bi"], ["data science", "statistics", "mathematics"], ["software"]),
 ("accounting", "Accountant", ["accounting", "trainee accountant", "graduate accountant", "bookkeeper", "audit associate"], ["accountancy", "accounting services", "bookkeeping", "audit services", "tax advisory", "payroll services"], ["acca", "aat", "bookkeeping", "financial reporting"], ["accounting", "accountancy", "finance"], ["financial_analysis"]),
 ("financial_analysis", "Financial analyst", ["finance analyst", "investment analyst"], ["investment research", "financial analysis services"], ["financial modelling", "valuation", "excel"], ["finance", "economics"], ["accounting"]),
 ("legal", "Legal associate", ["lawyer", "solicitor", "paralegal", "legal assistant"], ["legal services", "legal advice", "solicitors", "law firm"], ["legal research", "contract law"], ["law", "llb"], ["compliance"]),
 ("nursing", "Nurse", ["registered nurse", "staff nurse", "nursing"], ["nursing care", "nursing services", "nursing agency"], ["nmc", "clinical care", "patient care"], ["nursing"], ["healthcare"]),
 ("healthcare", "Healthcare assistant", ["health care assistant", "care assistant", "support worker", "care worker"], ["domiciliary care", "personal care", "healthcare support", "dementia care"], ["patient support", "personal care"], ["health and social care"], []),
 ("marketing", "Marketing specialist", ["marketing assistant", "digital marketer", "marketing executive"], ["marketing services", "digital marketing", "advertising agency", "brand strategy"], ["seo", "content marketing", "campaigns"], ["marketing"], ["design"]),
 ("hr", "Human resources specialist", ["hr specialist", "hr advisor", "hr assistant", "human resources"], ["hr consultancy", "human resources consulting"], ["employee relations", "recruitment", "cipd"], ["human resources"], ["recruitment"]),
 ("recruitment", "Recruitment consultant", ["recruiter", "talent acquisition specialist"], ["recruitment services", "staffing agency"], ["candidate sourcing", "recruitment"], ["human resources", "business"], ["hr"]),
 ("architecture", "Architect", ["architectural assistant", "architectural designer"], ["architectural design", "architectural services", "architectural practice"], ["revit", "bim", "design"], ["architecture"], ["civil"]),
 ("design", "Graphic designer", ["graphic design", "visual designer", "brand designer"], ["graphic design", "visual design", "branding services"], ["adobe", "illustration", "typography"], ["graphic design", "visual communication"], ["marketing"]),
 ("education", "Teacher", ["school teacher", "primary teacher", "secondary teacher", "educator"], ["school education", "teaching", "educational services"], ["lesson planning", "qts", "teaching"], ["education", "teaching"], []),
 ("research", "Research scientist", ["researcher", "laboratory scientist", "materials scientist"], ["scientific research", "materials testing", "laboratory research"], ["research", "laboratory", "experimental design"], ["chemistry", "physics", "materials science"], []),
 ("pharmacy", "Pharmacist", ["pharmacy", "clinical pharmacist"], ["pharmacy services", "dispensing medicines"], ["gphc", "pharmaceutical care"], ["pharmacy"], []),
 ("psychology", "Psychologist", ["clinical psychologist", "psychology"], ["psychological services", "clinical psychology"], ["psychological assessment", "hcpc"], ["psychology"], []),
 ("logistics", "Supply chain specialist", ["logistics coordinator", "supply chain analyst", "logistics manager"], ["logistics services", "supply chain management", "freight forwarding"], ["inventory", "supply chain", "procurement"], ["supply chain", "logistics"], []),
 ("project_management", "Project coordinator", ["project manager", "project management"], ["project management services", "project delivery consultancy"], ["project planning", "prince2", "stakeholder management"], ["project management"], []),
 ("technical_sales", "Technical sales engineer", ["technical sales", "sales engineer"], ["technical sales", "engineering sales"], ["engineering", "technical communication"], ["engineering"], []),
 ("compliance", "Compliance specialist", ["compliance officer", "risk analyst"], ["compliance consulting", "regulatory advisory"], ["regulatory compliance", "risk assessment"], ["law", "finance"], ["legal"]),
 ("hospitality", "Chef", ["cook", "sous chef", "chef de partie"], ["restaurant", "food preparation", "catering services"], ["food preparation", "culinary", "food safety"], ["culinary arts", "hospitality"], []),
]

# Equivalent service wording found in the CSV. These are professional services,
# not generic sectors or assumptions about every company's internal departments.
ACTIVITY_SYNONYMS = {
    'mechanical': ['mechanical engineering', 'mechanical engineering design'],
    'electrical': ['electronic engineering', 'electrical systems design'],
    'software': ['custom software', 'software engineering', 'mobile app development'],
    'accounting': ['tax preparation', 'tax return preparation', 'accounting and tax services'],
    'legal': ['legal consultancy', 'legal representation'],
    'healthcare': ['home care', 'residential care', 'supported living', 'care at home'],
    'marketing': ['seo services', 'search engine optimisation', 'search engine optimization', 'social media marketing', 'advertising services'],
    'hr': ['hr consulting', 'hr services', 'human resources consultancy'],
    'recruitment': ['recruitment agency', 'recruitment consultancy'],
    'design': ['brand design', 'logo design'],
    'pharmacy': ['community pharmacy', 'online pharmacy', 'prescription services'],
    'hospitality': ['catering'],
}


class Taxonomy:
    def __init__(self, concepts=None):
        self.concepts = concepts or [Concept("bootstrap:" + s[0], s[1], s[2], list(dict.fromkeys(s[3]+ACTIVITY_SYNONYMS.get(s[0],[]))), s[4], s[5], ["bootstrap:" + x for x in s[6]]) for s in SEEDS]
        self.by_id = {c.id: c for c in self.concepts}
        self.version = "|".join(sorted({c.version for c in self.concepts}))
        from collections import Counter
        self.token_frequency=Counter(w for c in self.concepts for w in set(key(" ".join([c.label,*c.aliases])).split()))
        self.alias_index={}
        self.function_phrases={}
        self.activity_phrases={}
        for concept in self.concepts:
            for label in [concept.label,*concept.aliases]:
                self.alias_index.setdefault(key(label),concept)
                p=key(label)
                if p:
                    for phrase in [p,p+"s",p[:-1]+"ies" if p.endswith("y") else p]:
                        self.function_phrases.setdefault(phrase,set()).add(concept.id)
            for activity in concept.activities:
                self.activity_phrases.setdefault(key(activity),set()).add(concept.id)
        self.max_phrase_words=min(12,max((len(p.split()) for p in self.function_phrases),default=1))

    def resolve(self, label):
        # Stage prefixes do not create a different profession. Imported SOC title
        # aliases can otherwise mask the supported base concept (e.g. senior
        # software engineer resolving to a broad SOC concept with no activities).
        simplified=re.sub(r"^(senior|junior|graduate|trainee|entry level)\s+","",key(label))
        if simplified!=key(label):
            base=self.resolve(simplified)
            if base:
                return base
        exact=self.alias_index.get(key(label))
        if exact:
            return exact
        # Unknown niches retain their text rather than being forced into a broad role.
        return None

    def inferred_concepts(self, text, kind="function"):
        lookup=self.function_phrases if kind=="function" else self.activity_phrases
        tokens=key(text).split()
        found=set()
        for start in range(len(tokens)):
            for length in range(1,min(self.max_phrase_words,len(tokens)-start)+1):
                found.update(lookup.get(" ".join(tokens[start:start+length]),()))
        return sorted(found)

    def normalize(self, profile: Profile):
        suggestions, clarification = [], None
        if profile.explore:
            background = profile.background.subject + " " + profile.background.specialization
            suggestions = [RoleIntent(raw_label=c.label, concept_id=c.id) for c in self.concepts if any(contains(background, b) for b in c.backgrounds)][:3]
            clarification = "Choose the career paths you want to explore." if suggestions else "What kind of work would you like to do? Give a role or describe its responsibilities."
        else:
            for role in profile.role_intents:
                concept = self.resolve(role.raw_label)
                if role.concept_id and (not concept or concept.id != role.concept_id):
                    role = role.model_copy(update={"concept_id": None, "confirmed": False})
                if key(role.raw_label) in {"analyst", "engineer", "consultant", "manager", "business", "graduate"} and not (profile.skills or profile.experience_summary):
                    clarification = f"Which area of {role.raw_label.lower()} work interests you? For example, a specialization or the tasks you want to do."
                suggestions.append(role.model_copy(update={"concept_id": concept.id if concept else None}))
        return {"role_intents": [s.model_dump() for s in suggestions], "clarification": clarification, "taxonomy_version": self.version, "unknown_roles": [s.raw_label for s in suggestions if not s.concept_id]}

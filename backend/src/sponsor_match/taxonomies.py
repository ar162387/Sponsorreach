"""Versioned official artifacts; cross-taxonomy equivalence is never inferred."""
import csv
import io
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .evidence import fetch_public
from .ingest import artifact
from .taxonomy import Concept,Taxonomy

ONS_PAGE="https://www.ons.gov.uk/methodology/classificationsandstandards/standardoccupationalclassificationsoc/standardoccupationalclassificationsocextensionproject"


def decoded(data):
    try:return data.decode("utf-8-sig")
    except UnicodeDecodeError:return data.decode("cp1252")


def safe_zip(data):
    archive=zipfile.ZipFile(io.BytesIO(data))
    if sum(i.file_size for i in archive.infolist())>100_000_000:
        raise ValueError("Taxonomy archive exceeds the size limit")
    return archive


def import_ons(db,path,url,version):
    archive=safe_zip(Path(path).read_bytes())
    framework=next((n for n in archive.namelist() if n.lower().endswith("framework.csv")),None)
    if not framework:raise ValueError("Missing ONS Extended_SOC_framework.csv")
    text=decoded(archive.read(framework))
    lines=text.splitlines()
    start=next(i for i,line in enumerate(lines) if "Unique ID" in line and "Group Title" in line)
    concepts=[]
    for row in csv.DictReader(io.StringIO("\n".join(lines[start:]))):
        code=(row.get("Sub-Unit Group") or row.get("Unit Group") or "").strip()
        label=(row.get("Group Title") or "").strip()
        if not code or not label:continue
        id="uk-soc-2020:"+code.replace("/","")
        aliases=[]
        if label.endswith("s") and not label.endswith("ss"):aliases.append(label[:-1])
        concepts.append(Concept(id,label,aliases,[],[],[],[],version=version,metadata={"authority":"ONS","code":code,"four_digit_parent":code[:4],"source_url":url,"unique_id":row.get("Unique ID")}))
    if not concepts:raise ValueError("No occupations found")
    artifact(db,path,"taxonomy","ons:extended-soc",url,metadata={"version":version,"concepts":len(concepts)})
    db.seed_taxonomy(Taxonomy(concepts))
    return {"occupation_groups_imported":len(concepts),"version":version,"automatic_visa_classifications":0}


def fetch_ons(db,output):
    html,_,_=fetch_public(ONS_PAGE)
    soup=BeautifulSoup(html,"html.parser")
    urls=sorted({urljoin(ONS_PAGE,a["href"]) for a in soup.select("a[href]") if "structure and descriptions (zip)" in a.get_text().casefold()})
    if len(urls)!=1:raise ValueError("Cannot identify a unique official ONS structure download")
    match=re.search(r"(\d{8})\.zip",urls[0])
    if not match:raise ValueError("ONS structure download has no version date")
    version=match[1]
    data,final,_=fetch_public(urls[0],limit=10_000_000)
    folder=Path(output);folder.mkdir(parents=True,exist_ok=True)
    target=folder/("ons-extended-soc-"+version+".zip")
    target.write_bytes(data)
    result=import_ons(db,target,final,version)
    index_urls=sorted({urljoin(ONS_PAGE,a["href"]) for a in soup.select("a[href]") if "codingindexzip" in a["href"] and a["href"].endswith(".zip")})
    index_url=next((u for u in index_urls if "v2.zip" in u),index_urls[0] if index_urls else None)
    if not index_url:raise ValueError("ONS coding index download is missing")
    index_data,index_final,_=fetch_public(index_url,limit=10_000_000)
    index_path=folder/("ons-coding-index-"+version+".zip")
    index_path.write_bytes(index_data)
    result.update(import_ons_index(db,index_path,index_final,version))
    return result


def import_ons_index(db,path,url,version):
    archive=safe_zip(Path(path).read_bytes())
    name=next((n for n in archive.namelist() if "codingindex" in n.casefold() and n.casefold().endswith(".csv")),None)
    if not name:raise ValueError("Missing ONS coding index CSV")
    rows=list(csv.DictReader(io.StringIO(decoded(archive.read(name)))))
    mappings=defaultdict(set)
    qualified=defaultdict(set)
    for row in rows:
        code=(row.get("SOC_2020_ext") or row.get("SOC_2020") or "").replace("/","").strip()
        title=(row.get("INDEXOCC_-_natural_word_order") or "").strip()
        if not code or not title:continue
        mappings[title].add("uk-soc-2020:"+code)
        qualifiers=" ".join((row.get(k) or "").strip() for k in ["ADD","IND"]).strip()
        if qualifiers:qualified[title+" ("+qualifiers+")"].add("uk-soc-2020:"+code)
    concepts=[c for c in db.taxonomy().concepts if c.id.startswith("uk-soc-2020:")]
    by_id={c.id:c for c in concepts}
    added=0
    for title,codes in {**mappings,**qualified}.items():
        if len(codes)!=1:continue
        concept=by_id.get(next(iter(codes)))
        if concept and title not in concept.aliases:
            concept.aliases.append(title);added+=1
    db.seed_taxonomy(Taxonomy(concepts))
    artifact(db,path,"taxonomy","ons:coding-index",url,metadata={"version":version,"records":len(rows),"unambiguous_aliases":added})
    return {"coding_index_rows":len(rows),"occupation_aliases_added":added,"ambiguous_unqualified_titles":sum(len(ids)>1 for ids in mappings.values())}

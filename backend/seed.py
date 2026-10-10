"""Normalize the supplied CSV. Adapted dialogue is explicitly demo-authored.

Source CSV and original rubric are preserved in samples/. No clinical values
or units are inferred. Topic rules and learning checkpoints are app-authored.
"""
import json
from pathlib import Path
from .engine import TOPICS

ROOT=Path(__file__).resolve().parent.parent

def seed_profiles():
    rows=json.loads((ROOT/'data/raw_patients.json').read_text())
    details={
      'Vladko':[
        ('social','Lifestyle history','Smokes one pack of cigarettes per day; consumes 2–8 hard drinks on 2–6 nights per week; intranasal cocaine 1–2 times per month.','I smoke one pack a day. I have 2 to 8 hard drinks on 2 to 6 nights per week, and use intranasal cocaine 1 to 2 times per month.'),
        ('social','Sexual history','Sexually active primarily with men; inconsistent condom use.','I’m sexually active primarily with men, and I don’t always use condoms.'),
        ('diet','Diet','Vegetarian.','I follow a vegetarian diet.'),
        ('perspective','Support and adjustment','Recent immigrant with a demanding creative career and limited local support.','I moved recently, my work is demanding, and I have limited support here.')],
      'Wyatt':[
        ('labs','Measurements from supplied notes','BMI 32; Total Chol 235; LDL 145. Lipid units and collection date are not supplied.','My case lists a BMI of 32, total cholesterol of 235, and LDL of 145. It does not include the lipid units or date.'),
        ('bowel','Bowel history','Constipation; avoids discussing it.','I have been struggling with constipation. It’s difficult for me to talk about.'),
        ('diet','Food preferences','Dislikes fruits and vegetables.','I don’t like fruits and vegetables.')],
      'Walter':[
        ('diet','Diet history','Source describes difficulty following the diet.','I have trouble sticking to the diet.'),
        ('perspective','Conversation preferences','Likes talking with physical therapists and nurses; dislikes students.','I like talking with the physical therapists and nurses.')],
      'Marcus':[
        ('concern','History duration','Living with heart failure for about one year.','I have been living with heart failure for about a year.'),
        ('diet','Appetite concern','Early satiety.','I feel full early when I eat.'),
        ('labs','Measurement from supplied notes','BMI 19; measurement date is not supplied.','The BMI recorded in my case is 19.'),
        ('perspective','Patient understanding','Uncertain about the role of diet in symptom control.','I’m not sure how my diet affects my symptoms.')],
      'Omar':[
        ('labs','Lipid values from supplied notes','Total Chol 260; LDL 195; HDL 30. Units and collection date are not supplied.','My case lists total cholesterol of 260, LDL of 195, and HDL of 30. It does not give the units or collection date.'),
        ('labs','Measurements from supplied notes','BMI 29; waist circumference 43 inches.','My recorded BMI is 29 and my waist measurement is 43 inches.'),
        ('medication','Medication perspective','Expresses discomfort with taking medications; no specific prescription is supplied.','I’m uncomfortable with taking medications. My case does not list a specific prescription.'),
        ('perspective','Learning needs','Needs support understanding cholesterol results and realistic dietary approaches.','I would like help understanding my cholesterol results and changes I could make to my diet.')],
      'Nisha':[
        ('perspective','Patient perspective','Emotionally overwhelmed; wants to understand every detail and asks providers questions.','I feel overwhelmed. I have questions, and I want to understand every detail.'),
        ('concern','Hospital experience','First hospitalization.','This is my first hospitalization.')],
      'Yvette':[
        ('labs','Measurements from supplied notes','Blood pressure 155/110 mmHg; BMI 34. Measurement date is not supplied.','My case lists blood pressure of 155 over 110 millimeters of mercury and a BMI of 34.'),
        ('diet','Sodium understanding','Confused about sodium and salt.','I’m confused about sodium and salt.'),
        ('perspective','Patient understanding','Struggles to understand medical explanations.','My doctor told me, but I didn’t understand what she said.')],
      'Dominic':[
        ('perspective','Patient perspective','Mistrusts authority and is skeptical of the healthcare system.','I find it hard to trust the healthcare system.'),
        ('background','Family context','Protective of younger siblings.','I’m protective of my younger siblings.')]
    }
    patients=[]
    for row in rows:
        first=row['patient-name'].split()[0]
        p={'id':row['patient-uuid'],'name':row['patient-name'],'age':int(row['age']),'gender':row['gender'],'summary':row['summary'],'background':row['background'],'persona':row['personality'],'source_notes':row['notes'],'image':f"/assets/patients/{row['patient-uuid']}.jpg",'version':1,'status':'published','provenance':'Organizer CSV; dialogue and disclosure rules adapted for this local demo.','source_refs':['faculty-provided-sample-patient-details.csv'],'facts':[],'objectives':[],'validation_notes':[]}
        def add(topic,label,record,patient_text,release='question'):
            p['facts'].append({'id':f'f{len(p["facts"])+1}','topic':topic,'label':label,'record':record,'patient_text':patient_text,'keywords':TOPICS[topic][:], 'release':release,'source':'Organizer CSV: summary/background/notes; app-authored dialogue'})
        add('concern','Presenting case',p['summary'],f"My case describes: {p['summary']}.",'initial')
        add('background','Personal background',p['background'],f"A little about me: {p['background']}.")
        for entry in details[first]:add(*entry)
        for f in p['facts']:
            if f['release']!='initial':
                p['objectives'].append({'id':'o'+f['id'][1:],'label':'Explore '+f['label'].lower(),'fact_ids':[f['id']],'suggestion':f"Ask a focused question about {f['label'].lower()} and clarify the response."})
        if first=='Marcus':p['validation_notes'].append('The original summary says “NYHA Stage C”; retained verbatim. Faculty should review the classification terminology.')
        if first in ['Omar','Wyatt']:p['validation_notes'].append('Lipid units and collection dates are absent in the source. No units or dates were inferred.')
        patients.append(p)
    return patients

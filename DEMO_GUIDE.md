# CTA-DEFACE: Live Demo Walkthrough Guide
## For Non-Technical Stakeholders

---

## 📋 Demo Overview

**Purpose:** Show in real-time how CTA-DEFACE works
**Duration:** 15-20 minutes
**Audience:** Hospital staff, administrators, radiologists
**Equipment:** Laptop with CTA-DEFACE already installed, projector/screen

**What you'll demonstrate:**
1. Folder setup
2. Running a defacing job
3. Viewing before/after images
4. Explaining what changed

---

## ✅ Pre-Demo Checklist (Do This Before the Presentation)

### 1. Preparation (30 minutes before)
- [ ] Test that CTA-DEFACE is installed and working
- [ ] Have sample DICOM files ready in `dicom_input/` folder
- [ ] Close unnecessary windows and applications
- [ ] Set computer to full brightness
- [ ] Increase font size for visibility (Windows: 125% zoom, Mac: larger text)
- [ ] Have a DICOM viewer installed (e.g., DICOM Viewer, MicroDicom)
- [ ] Test projector/screen connection

### 2. Sample Data Verification
```bash
# Check you have sample DICOM files
ls -la dicom_input/ | head -20

# Verify output directory exists
mkdir -p dicom_output

# Verify the pipeline script is ready
ls -la cta_deface_pipeline_multi2.py
```

### 3. Optional: Pre-Run (Recommended)
For a 5-10 minute demo, you might want to run the job once before the presentation and keep results ready. This ensures you have real output to show.

---

## 🎬 Demo Script: Step-by-Step

### PART 1: Introduction & Setup (3-4 minutes)

**What to Say:**
> "Let me show you how CTA-DEFACE works in action. I've already set up the software on this computer, and we have some sample CT scans ready to process."

**Actions:**
1. Open a file manager (Windows Explorer or Finder)
2. Navigate to: `C:\Users\[username]\Documents\CTA-DEFACE` (Windows) or `~/Documents/CTA-DEFACE` (Mac/Linux)
3. Show the three main folders:
   - **dicom_input/** — Contains the scan we're about to deface
   - **dicom_output/** — Where results will appear
   - **model/** — The "brain" that identifies faces

**Point Out:**
- "See this `dicom_input` folder? It contains 5 original CT scans"
- "The `dicom_output` folder is empty now—it's where we'll put the defaced versions"
- "The `model` folder contains the AI that learned to recognize facial structures"

---

### PART 2: Show the Original Scans (2-3 minutes)

**Actions:**
1. Open DICOM viewer
2. Load one scan from `dicom_input/img001.dcm`
3. Display it on screen

**What to Say:**
> "This is one of our original CT scans. Notice you can clearly see the patient's face—the nose, cheeks, chin, all visible. In medical imaging, this is normal and necessary for diagnosis. But if we wanted to share this scan with a medical school or research team, we'd need to remove these identifying features."

**Point Out to Audience:**
- The patient's facial features are clearly visible
- The scan shows other important clinical information (brain structure, etc.)
- Patient ID, scan date, and other metadata are visible in the header

---

### PART 3: Run the Defacing Pipeline (5-7 minutes)

**Actions:**

1. **Open Terminal/PowerShell:**
   - Windows: Right-click → Open PowerShell here
   - Mac/Linux: Right-click → Open Terminal here

2. **Show the activation command:**
   ```bash
   source .venv_cta_deface/bin/activate  # Linux/Mac
   # or
   .\.venv_cta_deface\Scripts\Activate.ps1  # Windows
   ```

   **Say:** "I'm activating the Python environment that has CTA-DEFACE and all its dependencies installed."

3. **Show the actual command:**
   ```bash
   python cta_deface_pipeline_multi2.py -i dicom_input -o dicom_output
   ```

   **Say:** "Now I'll run the defacing command. It's simple: just ask Python to run our pipeline script, saying 'take images from dicom_input and put results in dicom_output.'"

4. **Press Enter to run**

   **Watch the output:** Line by line, the script will show:
   ```
   Processing case: img001
   Converting DICOM to NIfTI...
   Running CTA-DEFACE AI...
   Converting back to DICOM...
   Done with case: img001
   ```

5. **Explain what's happening:**

   > "What you're seeing in real-time is the four-step process:
   > 1. **Read the scan** — Taking the DICOM file and reading it
   > 2. **AI Detection** — Running the AI to identify facial structures
   > 3. **Face Removal** — Replacing facial pixels with safe background
   > 4. **Convert back** — Saving it in the original DICOM format"

6. **Watch first scan complete (~3-5 minutes)**
   - Audience can see progress in real-time
   - Second and subsequent scans will process faster if you continue

**Pro Tips During Processing:**
- If processing seems slow, say: "This is running on CPU—with a GPU, it would be 5-10x faster"
- Point to the intermediate steps being shown: "Notice it's keeping track of each case, each conversion step"
- If questions come up, acknowledge but say "Let's see the results first"

---

### PART 4: View the Results (3-4 minutes)

**Actions:**

1. **Open File Manager and navigate to `dicom_output/`**

   **Say:** "Look—our defaced scans are now here in the output folder!"

2. **Show the files:**
   - Point out the same filenames as input (img001.dcm, img002.dcm, etc.)
   - Same file sizes
   - Same structure

3. **Open the defaced DICOM in viewer:**
   - Load `dicom_output/img001.dcm`
   - Display it beside or alternating with the original

4. **Side-by-Side Comparison:**
   
   **Original (from dicom_input):**
   - Facial features clearly visible
   - Face intact
   
   **Defaced (from dicom_output):**
   - Facial region replaced with blank/gray space
   - Rest of scan looks unchanged
   - Same patient ID, date, metadata visible

**What to Say:**
> "See the difference? The original scan on the left shows the complete face. The defaced version on the right has the facial region removed. 
> 
> But notice—all the clinical information stayed the same. The patient ID is still there. The scan date is still there. All the brain anatomy that doctors need is still visible. We only removed the face.
> 
> This happens automatically. No human edited these images. The AI identified exactly where the face was and removed it. No guess work, no manual labor."

**Point Out Key Details:**
- Original has visible facial profile
- Defaced image shows smooth background where face was
- Brain/skull structures still clearly visible
- All metadata (patient info, dates, scan parameters) preserved
- Image quality otherwise unchanged

---

### PART 5: Address Questions (2-3 minutes)

**Likely Questions & Answers:**

**Q: "How does it know what is a face?"**
A: "The AI was trained on thousands of real CT scans. It learned the patterns—what facial structures look like. Now when you show it a new scan, it recognizes those patterns and removes them."

**Q: "Could it accidentally remove something important?"**
A: "That's a great question. The AI is trained specifically on head/neck imaging, so it knows exactly what structures are facial anatomy versus what's part of the brain or neck. In testing, it's been very accurate. Of course, we'd recommend having a radiologist review a few samples for your specific use case."

**Q: "How long did that take?"**
A: "Each scan took about 3-5 minutes on this standard computer. With 50 scans, that's only a few hours of computer time. A person manually would take days."

**Q: "Can we get the original back if we need it?"**
A: "Yes! The original files are completely safe in the input folder. These defaced versions are separate copies. If you ever need the original, it's still there unchanged."

**Q: "What happens to the original data?"**
A: "You decide. You can keep the originals in a secure archive. You share the defaced versions with the research team. The originals never leaves your hospital."

**Q: "Does this work with our hospital's DICOM system?"**
A: "Yes, it works with standard DICOM files from any hospital system—CT, MRI, any imaging modality with head/neck data. The files format stays exactly the same."

---

## 📊 Demo Variants (Choose Based on Time)

### Quick Demo (10 minutes)
- Show folder setup (1 min)
- Show original scan (1 min)
- Run command and let it process one scan (5 min)
- Show partial results (2 min)
- Questions (1 min)

### Standard Demo (15-20 minutes)
- Full walkthrough as above
- Show 2-3 original scans
- Run 3-5 cases
- Show before/after comparison
- Answer questions

### Comprehensive Demo (30+ minutes)
- Full setup explanation
- Show how it integrates with existing DICOM systems
- Run full batch (10-50 scans)
- Show quality control process
- Discuss implementation strategy
- Extended Q&A

---

## 🖥️ Screen Setup Tips

### For Maximum Visibility:

1. **Increase zoom level:**
   - Windows: Settings → System → Display → Set to 125% or 150%
   - Mac: System Preferences → Displays → Resolution → Larger Text
   - Linux: Settings → Display → Scale to 150%

2. **Maximize window size:**
   - Full screen terminal
   - Large file manager windows

3. **Use high contrast:**
   - Dark terminal background, light text
   - Make file/folder names bold

4. **Font adjustments:**
   - Terminal font size: 18pt or larger
   - File manager: Icon view with large icons

---

## 🎯 Key Messages to Reinforce

**During the Demo, Make Sure to Emphasize:**

1. **Privacy is the Goal**
   - "We're protecting patient identity while keeping medical information"

2. **Completely Automated**
   - "No human editing needed—the AI does it all"

3. **Uses Your Existing Data Format**
   - "Scans come in as standard DICOM, go out as standard DICOM"

4. **Data Stays Secure**
   - "Everything processes on your own computer—no cloud, no external servers"

5. **Faster Than Manual**
   - "Hours of computer time instead of days of human work"

6. **Easy Integration**
   - "One command to process entire batches"

---

## ⚠️ Troubleshooting During Demo

### If Something Goes Wrong:

**"The script won't run / Python not found"**
- Solution: Verify venv is activated, show `python --version`
- Fallback: Show pre-recorded results instead

**"Processing is very slow"**
- Say: "This is normal on CPU. With a GPU, it would be 5-10x faster."
- Continue explanation while it processes

**"DICOM viewer won't open file"**
- Have a backup: Show screenshot of before/after comparison
- Still point out the differences

**"Output folder is empty after running"**
- Check: Did the script finish? Look for any error messages in terminal
- May need to wait a moment for files to write
- Fallback: Use pre-processed sample results

**"Image doesn't look quite right"**
- Normal: Different viewers display different brightness/contrast
- Reassure: "This is just how this viewer displays it. In your hospital system it will look normal"

---

## 📱 Backup Plan

**Have these ready in case of technical issues:**

1. **Screenshot folder** with before/after examples
2. **Video recording** of a previous successful run (30 seconds)
3. **Pre-processed output** ready to show
4. **Printed comparison images** (original vs. defaced)

These ensure even if live demo fails, you can still show the results clearly.

---

## 📋 Post-Demo: Next Steps to Mention

**After showing it works, tell them:**

> "If you're interested in using CTA-DEFACE for your hospital:
> 
> 1. **Test Phase** (1-2 weeks): Process a small batch of real patient scans with physician oversight
> 
> 2. **Quality Review** (1 week): Have your radiologists review samples to ensure accuracy for your needs
> 
> 3. **Compliance Check** (1 week): Work with IT/compliance to ensure it fits your security and HIPAA requirements
> 
> 4. **Training** (1-2 days): Quick training for staff who'll use it
> 
> 5. **Full Deployment** (1-2 weeks): Integrate into your regular data sharing workflow"

---

## 🎤 Presentation Delivery Tips

**Tone:**
- Keep it conversational, not technical jargon
- Use analogies: "It's like a smart eraser that only removes faces"
- Show enthusiasm for the technology

**Pacing:**
- Go slow enough people understand what's happening
- Speed up setup steps (people don't need to see folder navigation)
- Slow down during AI processing (good thinking time for audience)

**Engagement:**
- Ask rhetorical questions: "Notice anything about this scan?"
- Invite comments: "Anyone want to see it from a different angle?"
- Encourage questions: "Ask me anything as we go"

**Confidence:**
- Know your material—practice the demo once before
- If you don't know answer to question, be honest: "That's a great question, I'll find out for you"
- Show genuine interest in their concerns

---

## ✨ Success Criteria

**Demo went well if you accomplished:**

✓ Audience understands the problem (patient privacy in imaging)
✓ Audience sees the solution work in real-time
✓ Audience understands original data stays safe
✓ Audience sees clinical data is preserved
✓ Audience understands speed advantage
✓ Questions answered confidently
✓ Interest expressed in trying/piloting it
✓ No technical jargon confused people

---

## 📞 Reference: Command You'll Use

```bash
# Activate environment
source .venv_cta_deface/bin/activate

# Run the pipeline
python cta_deface_pipeline_multi2.py -i dicom_input -o dicom_output

# That's it!
```

**Output you'll see:**
```
Processing case: img001
Converting DICOM to NIfTI...
Running CTA-DEFACE...
Converting back to DICOM...
Completed: img001
```

---

## 📊 Timing Chart

**Typical Demo Timeline:**

| Part | Time | Activity |
|------|------|----------|
| Intro & welcome | 1 min | Set context |
| Setup explanation | 2-3 min | Show folders and AI model |
| Original scan review | 2 min | Display original DICOM |
| Run command | 1 min | Execute pipeline |
| Processing | 5-7 min | Watch it work (explain steps) |
| View results | 2-3 min | Show output, explain changes |
| Q&A | 2-3 min | Answer questions |
| **Total** | **15-20 min** | **Complete demo** |

---

## 🎓 Demo Variations by Audience

### For Hospital Administrators:
- **Emphasize:** Cost savings, speed, ease of implementation
- **Show:** Time comparison (manual vs. automated)
- **Ask:** "How many cases do you share per year?"

### For Radiologists/Clinicians:
- **Emphasize:** Clinical data preservation, accuracy, quality
- **Show:** Detailed before/after imagery
- **Ask:** "Does this look clinically appropriate?"

### For IT/Compliance:
- **Emphasize:** Local processing, no external servers, security
- **Show:** File format preservation, metadata handling
- **Ask:** "Any compliance concerns we should address?"

### For Research Teams:
- **Emphasize:** Reproducibility, batch processing, integration
- **Show:** Batch processing capability, output formats
- **Ask:** "How would this fit in your research workflow?"

---

## 🚀 Live Demo Checklist (Day Of)

**30 minutes before demo:**
- [ ] Test pipeline runs without errors
- [ ] Have sample DICOMs in dicom_input/
- [ ] Close all other applications
- [ ] Adjust screen zoom to 125-150%
- [ ] Test projector/screen visibility
- [ ] Have DICOM viewer ready
- [ ] Test terminal access

**At demo time:**
- [ ] Greet audience, set expectations
- [ ] Follow script as guide (not word-for-word)
- [ ] Make eye contact with audience
- [ ] Keep an eye on timing
- [ ] Be ready for questions
- [ ] Have backup materials ready

---

**Good luck with your demo! You've got this! 🎬**


# SIH Context

Smart India Hackathon 2026 is the target event for this project. Understanding SIH's structure is critical because every design decision — from [[Model Strategy|model selection]] to [[Approval Gate Design|approval gates]] — is optimized for generating SIH-ready projects.

## What is SIH?

> [!pipeline] Smart India Hackathon 2026
> India's largest hackathon. Government ministries and organizations post real-world problem statements. Student teams build working solutions in 36 hours. Winners get prizes, mentorship, and often government contracts to continue development.
>
> **Date:** August 18-19, 2026
> **Format:** 36-hour build sprint
> **Teams:** 6 members each
> **Judging:** Live demo + presentation to ministry representatives

## Problem Statements

SIH 2026 has **498 problem statements** across 15 themes, posted by government organizations.

### Key Characteristics

| Property | Details |
|----------|---------|
| **Total problems** | 498 |
| **Themes** | 15 (Agriculture, Defense, Health, Education, Smart Cities, etc.) |
| **Input length** | 1-3 sentences (often very short — as few as 11 characters) |
| **Organizations** | DRDO, ISRO, MoD, NIC, AICTE, MoHFW, and 20+ others |
| **Typical format** | "Design a system that [does X] for [government body]" |

### Why Short Inputs Matter

> [!decision] The Extrapolation Challenge
> SIH problem statements are notoriously vague. Examples:
> - "Smart waste management" (3 words)
> - "Blockchain-based land registry for rural India" (7 words)
> - "AI-powered crop disease detection using drone imagery" (8 words)
>
> Each of our 6 agents must **extrapolate** from minimal input. The [[CEO Agent]] is specifically designed to expand these short statements into full project briefs. The [[Researcher Agent]] searches for context that the problem statement omits. This extrapolation ability is the core value of the pipeline.

## 15 Themes

| # | Theme | Example Problems |
|---|-------|-----------------|
| 1 | Agriculture | Crop monitoring, soil analysis, market prediction |
| 2 | Defense & Security | Border surveillance, threat detection, logistics |
| 3 | Education | Personalized learning, exam systems, skill matching |
| 4 | Healthcare | Disease prediction, telemedicine, drug tracking |
| 5 | Smart Cities | Traffic management, waste collection, energy optimization |
| 6 | Finance | Fraud detection, digital payments, financial inclusion |
| 7 | Environment | Pollution monitoring, forest management, climate data |
| 8 | Transportation | Route optimization, vehicle tracking, safety |
| 9 | Governance | Citizen services, transparency, public feedback |
| 10 | Energy | Smart grids, renewable monitoring, consumption |
| 11 | Rural Development | Connectivity, water management, livelihood |
| 12 | Disaster Management | Early warning, resource allocation, communication |
| 13 | Heritage & Tourism | Digital preservation, tourist management, AR guides |
| 14 | Space & Science | Satellite data, research tools, astronomical analysis |
| 15 | Cyber Security | Threat intelligence, privacy tools, secure communication |

## Government Organizations

Key organizations that post problem statements:

| Org | Full Name | Typical Problems |
|-----|-----------|-----------------|
| **DRDO** | Defence Research and Development Organisation | Defense tech, surveillance |
| **ISRO** | Indian Space Research Organisation | Satellite data, space tech |
| **NIC** | National Informatics Centre | Government digitization |
| **AICTE** | All India Council for Technical Education | Education platforms |
| **MoHFW** | Ministry of Health and Family Welfare | Healthcare systems |
| **MoD** | Ministry of Defence | Security, logistics |
| **MeitY** | Ministry of Electronics and IT | Digital India initiatives |

## How Our Pipeline Handles SIH

Each agent is tuned for SIH-specific challenges:

| Agent | SIH Adaptation |
|-------|----------------|
| [[CEO Agent]] | Expands 1-3 sentence inputs into full briefs |
| [[Business Analyst Agent]] | Frames requirements around government stakeholders |
| [[Researcher Agent]] | Searches for existing govt initiatives and schemes |
| [[Architect Agent]] | Designs for hackathon-demo-ready architecture |
| [[Engineer Agent]] | Generates MVP code that runs in demo |
| [[PPT Agent]] | Creates judge-ready presentation narrative |

## Timeline

| Date | Milestone |
|------|-----------|
| **Now** | Pipeline development and testing |
| **Aug 15** | Feature freeze, focus on reliability |
| **Aug 18-19** | SIH 2026 hackathon |
| **Post-event** | [[V2 Vision]] development begins |

---

Related: [[Project Vision]], [[CEO Agent]], [[Researcher Agent]], [[Budget & Costs]], [[PPT Agent]], [[How It Works]]

#project #sih #hackathon

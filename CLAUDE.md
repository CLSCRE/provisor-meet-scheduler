# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Provisor Meet Scheduler — a meeting scheduling tool for **CLS CRE** (Commercial Lending Solutions), a commercial mortgage brokerage in Los Angeles, CA. Part of the CLS CRE AI automation workspace.

## Workspace Context

This project lives in the CLS CRE `Claude Code/` workspace alongside sibling projects:
- **Social Media Engine** — Content generation + Metricool scheduling (Python/FastAPI)
- **Golf Command Center** — Tee-time booking automation (React/Express + Python bots)
- **Reonomy** — CRE property search SPA (Next.js 14/TypeScript)
- **Cre Dev Tools - Skills** — 22 Claude skills for CRE financial analysis

## Workspace Conventions

These patterns are established across sibling projects:
- **Windows-first**: All Python scripts start with `sys.stdout.reconfigure(encoding="utf-8")` for Windows compatibility
- **Environment**: `.env` files for secrets, `.env.example` for templates — never commit `.env`
- **Python projects**: `requirements.txt` for deps, `PYTHONPATH=.` when running scripts from project root
- **Node projects**: Vite for frontend builds, Express for API servers
- **Database**: SQLite for local storage (portable, no external deps)
- **Deployment**: Vercel for frontends, GitHub Actions for scheduled automation
- **Timezone**: `America/Los_Angeles` (Pacific Time) unless otherwise specified
- **Broker**: Trevor Damyan, Commercial Mortgage Broker, CLS CRE, Los Angeles CA
- **Brand colors**: Navy `#153D63`, Gold `#C5A355`, White `#FFFFFF`

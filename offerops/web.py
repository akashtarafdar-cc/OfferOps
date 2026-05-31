from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .config import AppConfig, Settings
from .models import DomainJob, StepStatus
from .runner import OfferProvisioner
from .state import StateStore


INDEX = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OfferOps Control Room</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f4efe6;
      --bg-2: #fffaf2;
      --ink: #1a2433;
      --muted: #5e6d7f;
      --line: rgba(38, 52, 72, 0.12);
      --card: rgba(255, 252, 247, 0.86);
      --brand: #0f8c78;
      --brand-2: #df6f35;
      --brand-3: #214a88;
      --ok-bg: #daf4e7;
      --ok-fg: #0d694d;
      --warn-bg: #ebeef4;
      --warn-fg: #425164;
      --fail-bg: #ffe1da;
      --fail-fg: #a12b20;
      --shadow: 0 26px 60px rgba(26, 36, 51, 0.12);
      --glass: rgba(255,255,255,0.72);
      --input-bg: rgba(255,255,255,0.88);
      --panel-bg: rgba(244, 239, 230, 0.78);
      --hero-text: rgba(241, 247, 255, 0.84);
      --hero-chip: rgba(255,255,255,0.1);
      font-family: "Segoe UI", "Aptos", ui-sans-serif, sans-serif;
    }
    body[data-theme="dark"] {
      --bg: #09111c;
      --bg-2: #101b2b;
      --ink: #edf4ff;
      --muted: #95a5bb;
      --line: rgba(180, 207, 241, 0.14);
      --card: rgba(12, 21, 34, 0.82);
      --ok-bg: rgba(15, 140, 120, 0.18);
      --ok-fg: #7ce7c8;
      --warn-bg: rgba(111, 132, 165, 0.2);
      --warn-fg: #cbd8e9;
      --fail-bg: rgba(194, 65, 54, 0.22);
      --fail-fg: #ffb3aa;
      --shadow: 0 30px 80px rgba(0, 0, 0, 0.32);
      --glass: rgba(20, 31, 48, 0.72);
      --input-bg: rgba(10, 18, 30, 0.84);
      --panel-bg: rgba(18, 29, 46, 0.82);
      --hero-text: rgba(220, 234, 255, 0.84);
      --hero-chip: rgba(255,255,255,0.06);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(223, 111, 53, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(15, 140, 120, 0.18), transparent 24%),
        linear-gradient(180deg, var(--bg-2), var(--bg));
      min-height: 100vh;
      transition: background 0.35s ease, color 0.35s ease;
    }
    .shell {
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px 18px 48px;
    }
    .hero {
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(255,255,255,0.55);
      border-radius: 28px;
      background:
        linear-gradient(135deg, rgba(18, 31, 46, 0.96), rgba(33, 74, 136, 0.92)),
        linear-gradient(135deg, rgba(15, 140, 120, 0.25), rgba(223, 111, 53, 0.2));
      box-shadow: var(--shadow);
      padding: 34px;
      color: white;
      animation: riseIn 0.75s ease both;
    }
    .hero::after {
      content: "";
      position: absolute;
      inset: auto -10% -38% 38%;
      height: 240px;
      background: radial-gradient(circle, rgba(255,255,255,0.18), transparent 62%);
      transform: rotate(-10deg);
      pointer-events: none;
    }
    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      border-radius: 999px;
      background: var(--hero-chip);
      border: 1px solid rgba(255,255,255,0.18);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      backdrop-filter: blur(14px);
    }
    h1 {
      margin: 18px 0 10px;
      font-size: clamp(2rem, 4vw, 3.6rem);
      line-height: 1.04;
      letter-spacing: -0.04em;
      max-width: 760px;
    }
    .hero p {
      margin: 0;
      max-width: 760px;
      color: var(--hero-text);
      font-size: 1.02rem;
      line-height: 1.6;
    }
    .hero-topbar {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      flex-wrap: wrap;
    }
    .hero-stats {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-top: 24px;
      max-width: 720px;
    }
    .stat {
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(255,255,255,0.08);
      border: 1px solid rgba(255,255,255,0.12);
      backdrop-filter: blur(16px);
      animation: fadeUp 0.7s ease both;
    }
    .stat strong {
      display: block;
      font-size: 1.35rem;
      margin-bottom: 4px;
    }
    .grid {
      display: grid;
      grid-template-columns: 430px minmax(0, 1fr);
      gap: 20px;
      margin-top: 22px;
      align-items: start;
    }
    .card {
      background: var(--card);
      border: 1px solid rgba(255,255,255,0.8);
      border-radius: 24px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
      transition: transform 0.25s ease, border-color 0.25s ease, background 0.35s ease;
      animation: fadeUp 0.7s ease both;
    }
    .card:hover { transform: translateY(-2px); }
    .panel {
      padding: 24px;
    }
    .panel h2 {
      margin: 0 0 8px;
      font-size: 1.3rem;
      letter-spacing: -0.03em;
    }
    .panel p {
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.55;
    }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }
    .field {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .field.full { grid-column: 1 / -1; }
    label {
      font-size: 0.92rem;
      font-weight: 700;
      color: var(--ink);
    }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 13px 14px;
      background: var(--input-bg);
      color: var(--ink);
      font: inherit;
      transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
    }
    textarea {
      min-height: 150px;
      resize: vertical;
    }
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: rgba(33, 74, 136, 0.45);
      box-shadow: 0 0 0 4px rgba(33, 74, 136, 0.08);
      transform: translateY(-1px);
    }
    .hint {
      color: var(--muted);
      font-size: 0.84rem;
      line-height: 1.45;
    }
    .toggle-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 4px;
    }
    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: var(--glass);
      font-size: 0.92rem;
    }
    .toggle input { width: auto; margin: 0; }
    .cta-row {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
      align-items: center;
    }
    button {
      appearance: none;
      border: 0;
      border-radius: 16px;
      padding: 14px 18px;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
      transition: transform 0.18s ease, opacity 0.18s ease, box-shadow 0.18s ease;
    }
    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.55; cursor: wait; transform: none; }
    .primary {
      background: linear-gradient(135deg, var(--brand), #16765f);
      color: white;
      box-shadow: 0 18px 35px rgba(15, 140, 120, 0.22);
    }
    .secondary {
      background: rgba(33, 74, 136, 0.08);
      color: var(--brand-3);
      border: 1px solid rgba(33, 74, 136, 0.15);
    }
    .badge, .status {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 82px;
      padding: 7px 11px;
      border-radius: 999px;
      font-size: 0.74rem;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .done { background: var(--ok-bg); color: var(--ok-fg); }
    .running { background: rgba(15, 140, 120, 0.15); color: var(--brand); }
    .failed { background: var(--fail-bg); color: var(--fail-fg); }
    .pending, .skipped { background: var(--warn-bg); color: var(--warn-fg); }
    .split {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
      gap: 18px;
    }
    .empty {
      min-height: 360px;
      display: grid;
      place-items: center;
      text-align: center;
      padding: 26px;
      color: var(--muted);
      animation: fadeIn 0.5s ease both;
    }
    .run-header {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 14px;
    }
    .run-header h3 {
      margin: 0;
      font-size: 1.15rem;
    }
    .progress-rail {
      height: 10px;
      border-radius: 999px;
      background: rgba(33, 74, 136, 0.09);
      overflow: hidden;
      margin: 16px 0 18px;
    }
    .progress-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--brand), var(--brand-2));
      transition: width 0.3s ease;
      position: relative;
      overflow: hidden;
    }
    .progress-fill::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.35), transparent);
      animation: sweep 1.9s linear infinite;
    }
    .job-list {
      display: grid;
      gap: 12px;
      margin-top: 12px;
    }
    .job {
      border: 1px solid rgba(38, 52, 72, 0.08);
      border-radius: 18px;
      padding: 15px 16px;
      background: var(--glass);
      animation: fadeUp 0.5s ease both;
    }
    .job-top {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      margin-bottom: 10px;
    }
    .job-title {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .job-title strong { font-size: 1rem; }
    .job-title span { color: var(--muted); font-size: 0.88rem; }
    .steps {
      display: grid;
      gap: 8px;
    }
    .step {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 10px;
      align-items: start;
      padding: 10px 12px;
      border-radius: 14px;
      background: var(--panel-bg);
      border: 1px solid rgba(38, 52, 72, 0.06);
      transition: transform 0.2s ease, background 0.35s ease;
    }
    .step:hover { transform: translateX(2px); }
    .step strong {
      display: block;
      margin-bottom: 3px;
      text-transform: capitalize;
    }
    .step code {
      display: block;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      color: var(--muted);
      font-size: 0.85rem;
    }
    .credentials {
      display: grid;
      gap: 12px;
    }
    .cred-card {
      padding: 16px;
      border-radius: 18px;
      background: linear-gradient(180deg, var(--card), var(--panel-bg));
      border: 1px solid rgba(38, 52, 72, 0.08);
      animation: fadeUp 0.6s ease both;
    }
    .cred-card h4 {
      margin: 0 0 12px;
      font-size: 1rem;
    }
    .cred-card-header {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 12px;
    }
    .cred-grid {
      display: grid;
      gap: 10px;
    }
    .cred-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 10px;
      align-items: center;
      padding: 10px 0;
      border-top: 1px solid rgba(38, 52, 72, 0.08);
    }
    .cred-row:first-child { border-top: 0; padding-top: 0; }
    .cred-content {
      display: grid;
      gap: 4px;
      min-width: 0;
    }
    .cred-row span {
      font-size: 0.76rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }
    .cred-row code {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      font-size: 0.95rem;
      color: var(--ink);
    }
    .mini-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .mini-button {
      appearance: none;
      border: 1px solid rgba(33, 74, 136, 0.14);
      background: rgba(33, 74, 136, 0.06);
      color: var(--brand-3);
      border-radius: 12px;
      padding: 8px 10px;
      font: inherit;
      font-size: 0.82rem;
      font-weight: 700;
      cursor: pointer;
    }
    .mini-button.copy-ok {
      background: rgba(15, 140, 120, 0.12);
      color: var(--brand);
      border-color: rgba(15, 140, 120, 0.18);
    }
    .history {
      display: grid;
      gap: 10px;
      margin-top: 14px;
      max-height: 360px;
      overflow: auto;
      padding-right: 2px;
    }
    .history-item {
      padding: 14px 16px;
      border-radius: 16px;
      background: var(--glass);
      border: 1px solid rgba(38, 52, 72, 0.08);
    }
    .history-item strong {
      display: block;
      margin-bottom: 6px;
    }
    .history-item span {
      display: inline-block;
      margin-right: 8px;
      color: var(--muted);
      font-size: 0.88rem;
    }
    .inline-note {
      margin-top: 12px;
      padding: 12px 14px;
      border-radius: 14px;
      background: rgba(33, 74, 136, 0.06);
      color: var(--brand-3);
      font-size: 0.9rem;
    }
    body[data-theme="dark"] .inline-note,
    body[data-theme="dark"] .mini-button,
    body[data-theme="dark"] .secondary {
      color: #d7e5ff;
      background: rgba(117, 157, 219, 0.12);
      border-color: rgba(117, 157, 219, 0.16);
    }
    body[data-theme="dark"] .card,
    body[data-theme="dark"] .job,
    body[data-theme="dark"] .history-item,
    body[data-theme="dark"] .toggle {
      border-color: rgba(180, 207, 241, 0.09);
    }
    body[data-theme="dark"] .stat {
      background: rgba(255,255,255,0.05);
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
      }
    }
    .theme-fab-wrap {
      position: fixed;
      right: 26px;
      bottom: 24px;
      z-index: 20;
      display: block;
    }
    .theme-toggle {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 58px;
      height: 47px;
      margin-left: auto;
      border-radius: 18px;
      border: 1px solid #e2e8f0;
      background: rgba(255, 255, 255, 0.98);
      color: #334155;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      backdrop-filter: blur(18px);
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.12);
      transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
    }
    .theme-toggle:hover {
      transform: translateY(-1px);
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.16);
      background: #f8fafc;
    }
    body[data-theme="dark"] .theme-toggle {
      border-color: rgba(51, 65, 85, 0.95);
      background: rgba(15, 23, 42, 0.96);
      color: #e2e8f0;
      box-shadow: 0 12px 28px rgba(2, 6, 23, 0.34);
    }
    body[data-theme="dark"] .theme-toggle:hover {
      background: rgba(30, 41, 59, 0.96);
    }
    .theme-toggle-icon {
      width: 20px;
      height: 20px;
      display: none;
    }
    .theme-toggle-icon.active {
      display: block;
    }
    .theme-toggle-auto {
      position: relative;
      width: 20px;
      height: 20px;
      display: none;
    }
    .theme-toggle-auto.active {
      display: block;
    }
    .theme-toggle-auto svg {
      width: 100%;
      height: 100%;
      display: block;
    }
    .theme-toggle-auto-badge {
      position: absolute;
      right: -4px;
      top: -4px;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: linear-gradient(135deg, #8e96ff, #6a6fff);
    }
    .theme-menu {
      position: absolute;
      right: 0;
      bottom: 88px;
      width: 248px;
      padding: 10px;
      border-radius: 24px;
      background: rgba(255, 255, 255, 0.98);
      border: 1px solid rgba(226, 232, 240, 0.95);
      color: #0f172a;
      box-shadow: 0 24px 50px rgba(15, 23, 42, 0.18);
      backdrop-filter: blur(18px);
      opacity: 0;
      transform: translateY(12px) scale(0.95);
      transform-origin: bottom right;
      pointer-events: none;
      transition: opacity 0.22s ease, transform 0.22s ease;
    }
    .theme-menu.open {
      opacity: 1;
      transform: translateY(0) scale(1);
      pointer-events: auto;
    }
    .theme-menu-label {
      margin-bottom: 8px;
      padding: 4px 8px 0;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: #94a3b8;
    }
    .theme-options {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .theme-option {
      display: grid;
      gap: 12px;
      justify-items: center;
      align-content: center;
      min-height: 82px;
      padding: 12px 8px;
      border-radius: 16px;
      border: 1px solid transparent;
      background: transparent;
      color: #334155;
      cursor: pointer;
      transition: background 0.2s ease, border-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
    }
    .theme-option:hover {
      transform: translateY(-1px);
      background: #f8fafc;
    }
    .theme-option.active {
      background: #eef2ff;
      color: #4f46e5;
      border-color: #c7d2fe;
      box-shadow: inset 0 0 0 1px rgba(199, 210, 254, 0.65);
    }
    .theme-option strong {
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0;
    }
    .theme-option-icon {
      width: 22px;
      height: 22px;
      position: relative;
      color: currentColor;
    }
    .theme-option-icon svg {
      width: 100%;
      height: 100%;
      display: block;
    }
    .theme-option-badge {
      position: absolute;
      right: -3px;
      top: -3px;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: linear-gradient(135deg, #8e96ff, #6a6fff);
    }
    .theme-menu-note {
      margin-top: 8px;
      padding: 0 8px 2px;
      color: #94a3b8;
      font-size: 11px;
      line-height: 1.4;
      text-align: center;
    }
    body[data-theme="dark"] .theme-menu {
      background: rgba(15, 23, 42, 0.96);
      border-color: rgba(51, 65, 85, 0.95);
      color: #e2e8f0;
      box-shadow: 0 24px 50px rgba(2, 6, 23, 0.42);
    }
    body[data-theme="dark"] .theme-menu-label,
    body[data-theme="dark"] .theme-menu-note {
      color: #94a3b8;
    }
    body[data-theme="dark"] .theme-option {
      color: #cbd5e1;
    }
    body[data-theme="dark"] .theme-option:hover {
      background: rgba(255,255,255,0.05);
    }
    body[data-theme="dark"] .theme-option.active {
      background: rgba(79, 70, 229, 0.18);
      color: #a5b4fc;
      border-color: rgba(129, 140, 248, 0.45);
      box-shadow: inset 0 0 0 1px rgba(129, 140, 248, 0.24);
    }
    .status.running,
    .badge.running {
      animation: pulseGlow 1.4s ease-in-out infinite;
    }
    @keyframes riseIn {
      from { opacity: 0; transform: translateY(16px) scale(0.99); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(14px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    @keyframes pulseGlow {
      0%, 100% { box-shadow: 0 0 0 0 rgba(15, 140, 120, 0.18); }
      50% { box-shadow: 0 0 0 8px rgba(15, 140, 120, 0.04); }
    }
    @keyframes sweep {
      from { transform: translateX(-120%); }
      to { transform: translateX(120%); }
    }
    @media (max-width: 1080px) {
      .grid, .split { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
      .shell { padding: 18px 12px 32px; }
      .hero, .panel { padding: 20px; }
      .hero-stats, .form-grid { grid-template-columns: 1fr; }
      .hero-topbar { align-items: stretch; }
      .theme-menu {
        width: min(316px, calc(100vw - 28px));
      }
      .theme-fab-wrap {
        right: 14px;
        bottom: 14px;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-topbar">
        <div class="eyebrow">OfferOps Control Room</div>
      </div>
      <h1>Provision domains from one clean screen instead of the terminal.</h1>
      <p>Select the server, enter the slug, paste one or many domains, and watch each infrastructure step advance in real time. When the run finishes, only the credentials you actually need are surfaced.</p>
      <div class="hero-stats">
        <div class="stat"><strong id="heroProfiles">0</strong><span>configured profiles</span></div>
        <div class="stat"><strong id="heroServers">0</strong><span>server targets</span></div>
        <div class="stat"><strong id="heroJobs">0</strong><span>saved jobs</span></div>
      </div>
    </section>

    <section class="grid">
      <div class="card panel">
        <h2>Start A Run</h2>
        <p>Choose the kind and server, then add the domain list and offer slug. The resolved profile is shown automatically so the operator never needs to touch CSV rows.</p>
        <form id="runForm">
          <div class="form-grid">
            <div class="field">
              <label for="kind">Stack</label>
              <select id="kind" required></select>
            </div>
            <div class="field">
              <label for="server">Server</label>
              <select id="server" required></select>
            </div>
            <div class="field full">
              <label for="profilePreview">Resolved Profile</label>
              <input id="profilePreview" readonly>
              <div class="hint">The app resolves the final profile from your stack and server choice.</div>
            </div>
            <div class="field full">
              <label for="slug">Slug / Offer Path</label>
              <input id="slug" placeholder="v1/msrack" required>
              <div class="hint">Enter only the path portion. Full URLs also work if pasted.</div>
            </div>
            <div class="field full">
              <label for="domains">Domains</label>
              <textarea id="domains" placeholder="example.com&#10;example.net&#10;example.org" required></textarea>
              <div class="hint">Paste one domain per line. Commas and spaces are also accepted.</div>
            </div>
          </div>
          <div class="toggle-row">
            <label class="toggle"><input type="checkbox" id="orangeBrowser" checked> Update Orange nameservers automatically</label>
            <label class="toggle"><input type="checkbox" id="dryRun"> Dry run only</label>
          </div>
          <div class="inline-note" id="runNote">Waiting for config...</div>
          <div class="cta-row">
            <button class="primary" id="submitButton" type="submit">Launch Provisioning</button>
            <button class="secondary" id="refreshButton" type="button">Refresh History</button>
          </div>
        </form>
      </div>

      <div class="split">
        <div class="card panel">
          <div id="runMount" class="empty">No active run yet. Start a run to see step-by-step progress here.</div>
        </div>
        <div class="card panel">
          <h2>Saved History</h2>
          <p>Recent saved jobs from the local state file remain visible here for quick reference.</p>
          <div id="history" class="history"></div>
        </div>
      </div>
    </section>

    <footer style="padding: 28px 10px 4px; text-align: center; color: var(--muted); line-height: 1.7;">
      <div>&copy; 2026 OfferOps Inc. All Rights Reserved.</div>
      <div>Created with ❤️ by Akash</div>
    </footer>
  </div>
  <div class="theme-fab-wrap">
    <div id="themeMenu" class="theme-menu">
      <div class="theme-menu-label">Theme</div>
      <div class="theme-options">
        <button class="theme-option" id="themeOptionLight" type="button" onclick="setThemeMode('light')">
          <span class="theme-option-icon sun">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <circle cx="12" cy="12" r="4"></circle>
              <path d="M12 2v2.5M12 19.5V22M4.93 4.93l1.77 1.77M17.3 17.3l1.77 1.77M2 12h2.5M19.5 12H22M4.93 19.07l1.77-1.77M17.3 6.7l1.77-1.77"></path>
            </svg>
          </span>
          <strong>Light</strong>
        </button>
        <button class="theme-option" id="themeOptionDark" type="button" onclick="setThemeMode('dark')">
          <span class="theme-option-icon moon">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
              <path d="M21 14.7A9 9 0 0 1 9.3 3a1 1 0 0 0-1.26 1.26A7 7 0 1 0 19.74 16a1 1 0 0 0 1.26-1.3Z"></path>
            </svg>
          </span>
          <strong>Dark</strong>
        </button>
        <button class="theme-option" id="themeOptionAuto" type="button" onclick="setThemeMode('auto')">
          <span class="theme-option-icon auto">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <rect x="3" y="4" width="18" height="12" rx="2"></rect>
              <path d="M8 20h8M12 16v4"></path>
            </svg>
            <span id="themeAutoBadge" class="theme-option-badge"></span>
          </span>
          <strong>Auto</strong>
        </button>
      </div>
      <div id="themeMenuNote" class="theme-menu-note">Using the current appearance.</div>
    </div>
    <button id="themeToggle" class="theme-toggle" type="button" aria-expanded="false" aria-controls="themeMenu" aria-label="Theme switcher" title="System theme">
      <svg id="themeToggleLight" class="theme-toggle-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <circle cx="12" cy="12" r="4"></circle>
        <path d="M12 2v2.5M12 19.5V22M4.93 4.93l1.77 1.77M17.3 17.3l1.77 1.77M2 12h2.5M19.5 12H22M4.93 19.07l1.77-1.77M17.3 6.7l1.77-1.77"></path>
      </svg>
      <svg id="themeToggleDark" class="theme-toggle-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
        <path d="M21 14.7A9 9 0 0 1 9.3 3a1 1 0 0 0-1.26 1.26A7 7 0 1 0 19.74 16a1 1 0 0 0 1.26-1.3Z"></path>
      </svg>
      <span id="themeToggleAuto" class="theme-toggle-auto">
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <rect x="3" y="4" width="18" height="12" rx="2"></rect>
          <path d="M8 20h8M12 16v4"></path>
        </svg>
        <span id="themeToggleAutoBadge" class="theme-toggle-auto-badge"></span>
      </span>
    </button>
  </div>
  <script>
    const state = {
      config: null,
      currentRunId: null,
      pollHandle: null,
      themeMode: 'auto',
      theme: 'light',
    };

    async function boot() {
      initializeTheme();
      await Promise.all([loadConfig(), loadHistory()]);
    }

    async function loadConfig() {
      const response = await fetch('/api/config');
      const config = await response.json();
      state.config = config;
      renderConfig(config);
    }

    function renderConfig(config) {
      const kindSelect = document.getElementById('kind');
      const serverSelect = document.getElementById('server');
      kindSelect.innerHTML = config.kinds.map(kind => `<option value="${escapeHtml(kind)}">${escapeHtml(titleize(kind))}</option>`).join('');
      updateServerOptions();
      document.getElementById('heroProfiles').textContent = String((config.profiles || []).length);
      document.getElementById('heroServers').textContent = String((config.servers || []).length);
      document.getElementById('runNote').textContent = 'Profile selection is now driven by dropdowns instead of CSV editing.';
      kindSelect.addEventListener('change', updateServerOptions);
      serverSelect.addEventListener('change', updateProfilePreview);
      updateProfilePreview();
    }

    function initializeTheme() {
      const stored = localStorage.getItem('offerops-theme-mode') || 'auto';
      const query = window.matchMedia('(prefers-color-scheme: dark)');
      state.themeMode = stored;
      applyTheme(resolveTheme(stored), false);
      syncThemeControls();
      const toggle = document.getElementById('themeToggle');
      const menu = document.getElementById('themeMenu');
      toggle.addEventListener('click', () => {
        const isOpen = menu.classList.toggle('open');
        toggle.setAttribute('aria-expanded', String(isOpen));
      });
      document.addEventListener('click', (event) => {
        if (!menu.contains(event.target) && !toggle.contains(event.target)) {
          menu.classList.remove('open');
          toggle.setAttribute('aria-expanded', 'false');
        }
      });
      query.addEventListener('change', () => {
        if (state.themeMode === 'auto') {
          applyTheme(resolveTheme('auto'), false);
          syncThemeControls();
        }
      });
    }

    function resolveTheme(mode) {
      if (mode === 'auto') {
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      }
      return mode === 'dark' ? 'dark' : 'light';
    }

    function setThemeMode(mode) {
      const nextMode = ['light', 'dark', 'auto'].includes(mode) ? mode : 'auto';
      const previousTheme = state.theme;
      state.themeMode = nextMode;
      localStorage.setItem('offerops-theme-mode', nextMode);
      applyTheme(resolveTheme(nextMode), previousTheme !== resolveTheme(nextMode));
      syncThemeControls();
    }

    function applyTheme(theme, animate = true) {
      const nextTheme = theme === 'dark' ? 'dark' : 'light';
      state.theme = nextTheme;
      document.body.setAttribute('data-theme', state.theme);
    }

    function syncThemeControls() {
      document.getElementById('themeOptionLight').classList.toggle('active', state.themeMode === 'light');
      document.getElementById('themeOptionDark').classList.toggle('active', state.themeMode === 'dark');
      document.getElementById('themeOptionAuto').classList.toggle('active', state.themeMode === 'auto');
      document.getElementById('themeToggleLight').classList.toggle('active', state.themeMode === 'light');
      document.getElementById('themeToggleDark').classList.toggle('active', state.themeMode === 'dark');
      document.getElementById('themeToggleAuto').classList.toggle('active', state.themeMode === 'auto');
      const toggle = document.getElementById('themeToggle');
      const toggleTitle = state.themeMode === 'auto'
        ? 'System theme'
        : (state.themeMode === 'dark' ? 'Dark theme' : 'Light theme');
      toggle.title = toggleTitle;
      toggle.setAttribute('aria-label', 'Theme switcher');
      const autoBadge = document.getElementById('themeAutoBadge');
      const toggleAutoBadge = document.getElementById('themeToggleAutoBadge');
      const badgeBackground = state.theme === 'dark'
        ? 'linear-gradient(135deg, #8e96ff, #6a6fff)'
        : 'linear-gradient(135deg, #fbbf24, #f59e0b)';
      if (autoBadge) {
        autoBadge.style.background = badgeBackground;
      }
      if (toggleAutoBadge) {
        toggleAutoBadge.style.background = badgeBackground;
      }
      const note = state.themeMode === 'auto'
        ? `Using ${state.theme} from your device`
        : `Using ${state.theme} appearance manually`;
      document.getElementById('themeMenuNote').textContent = note;
    }

    function updateServerOptions() {
      const kind = document.getElementById('kind').value;
      const serverSelect = document.getElementById('server');
      const servers = (state.config.server_choices || {})[kind] || [];
      serverSelect.innerHTML = servers.map(server => `<option value="${escapeHtml(server)}">${escapeHtml(titleize(server))}</option>`).join('');
      updateProfilePreview();
    }

    function updateProfilePreview() {
      const kind = document.getElementById('kind').value;
      const server = document.getElementById('server').value;
      const profile = ((state.config.profile_lookup || {})[kind] || {})[server] || '';
      document.getElementById('profilePreview').value = profile;
    }

    async function loadHistory() {
      const response = await fetch('/api/state');
      const payload = await response.json();
      const jobs = Object.values(payload.jobs || {});
      document.getElementById('heroJobs').textContent = String(jobs.length);
      const history = document.getElementById('history');
      if (!jobs.length) {
        history.innerHTML = '<div class="history-item">No saved jobs yet.</div>';
        return;
      }
      history.innerHTML = jobs.reverse().slice(0, 18).map(job => `
        <div class="history-item">
          <strong>${escapeHtml(job.domain)}</strong>
          <span>${escapeHtml(job.profile)}</span>
          <span class="status ${escapeHtml(job.status)}">${escapeHtml(job.status)}</span>
        </div>
      `).join('');
    }

    async function submitRun(event) {
      event.preventDefault();
      const body = {
        kind: document.getElementById('kind').value,
        server: document.getElementById('server').value,
        offer_path: document.getElementById('slug').value.trim(),
        domains: document.getElementById('domains').value,
        orange_browser: document.getElementById('orangeBrowser').checked,
        dry_run: document.getElementById('dryRun').checked,
      };
      setRunningState(true);
      document.getElementById('runNote').textContent = 'Provisioning started. Live updates will appear on the right.';
      const response = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) {
        setRunningState(false);
        document.getElementById('runNote').textContent = payload.error || 'Unable to start the run.';
        return;
      }
      state.currentRunId = payload.run_id;
      await pollRun();
      if (state.pollHandle) {
        clearInterval(state.pollHandle);
      }
      state.pollHandle = setInterval(pollRun, 1200);
    }

    async function pollRun() {
      if (!state.currentRunId) return;
      const response = await fetch(`/api/runs/${encodeURIComponent(state.currentRunId)}`);
      const payload = await response.json();
      if (!response.ok) {
        document.getElementById('runNote').textContent = payload.error || 'Unable to load run progress.';
        return;
      }
      renderRun(payload);
      if (payload.status !== 'running') {
        clearInterval(state.pollHandle);
        state.pollHandle = null;
        setRunningState(false);
        loadHistory();
      }
    }

    function renderRun(run) {
      const mount = document.getElementById('runMount');
      const jobs = run.jobs || [];
      const total = jobs.length || 1;
      const completed = jobs.filter(job => job.status === 'done' || job.status === 'failed').length;
      const progress = Math.round((completed / total) * 100);
      mount.className = '';
      mount.innerHTML = `
        <div class="run-header">
          <div>
            <h3>${escapeHtml(run.profile || 'Run')}</h3>
            <div class="hint">${escapeHtml(run.status_message || '')}</div>
          </div>
          <span class="status ${escapeHtml(run.status)}">${escapeHtml(run.status)}</span>
        </div>
        <div class="progress-rail"><div class="progress-fill" style="width:${progress}%"></div></div>
        <div class="job-list">${jobs.map(renderJob).join('')}</div>
      `;
      document.getElementById('runNote').textContent = run.status === 'running'
        ? (run.status_message || 'Run in progress.')
        : 'Run finished. Final credentials are shown in the result cards.';
    }

    function renderJob(job) {
      const encodedCredentials = encodeCredentialArg(job.credentials);
      const credentials = job.credentials ? `
        <div class="credentials">
          <div class="cred-card">
            <div class="cred-card-header">
              <h4>Required Credentials</h4>
              <div class="mini-actions">
                <button class="mini-button" type="button" onclick='copyCredentialBundle(this, ${JSON.stringify(encodedCredentials)})'>Copy All</button>
                <button class="mini-button" type="button" onclick='downloadCredentialBundle(${JSON.stringify(encodedCredentials)}, ${JSON.stringify(job.domain || 'credentials')})'>Export JSON</button>
              </div>
            </div>
            <div class="cred-grid">
              ${renderCredential('cPanel Username', job.credentials.cpanel_username)}
              ${renderCredential('cPanel Password', job.credentials.cpanel_account_password || 'Existing account password not re-shown')}
              ${renderCredential('Support Email', job.credentials.support_email)}
              ${renderCredential('Support Email Password', job.credentials.support_email_password)}
              ${renderCredential('Database Name', job.credentials.database_name)}
              ${renderCredential('Database User', job.credentials.database_user)}
              ${renderCredential('Database Password', job.credentials.database_user_password)}
              ${renderCredential('Nameservers', (job.credentials.nameservers || []).join(', '))}
            </div>
          </div>
        </div>
      ` : '';

      return `
        <article class="job">
          <div class="job-top">
            <div class="job-title">
              <strong>${escapeHtml(job.domain)}</strong>
              <span>${escapeHtml(job.profile)}</span>
            </div>
            <span class="status ${escapeHtml(job.status)}">${escapeHtml(job.status)}</span>
          </div>
          <div class="steps">${(job.steps || []).map(renderStep).join('')}</div>
          ${credentials}
        </article>
      `;
    }

    function renderStep(step) {
      return `
        <div class="step">
          <span class="badge ${escapeHtml(step.status)}">${escapeHtml(step.status)}</span>
          <div>
            <strong>${escapeHtml(step.name.replaceAll('-', ' '))}</strong>
            <code>${escapeHtml(step.message || '')}</code>
          </div>
        </div>
      `;
    }

    function renderCredential(label, value) {
      if (value === undefined || value === null || value === '') return '';
      const encodedValue = JSON.stringify(String(value));
      return `
        <div class="cred-row">
          <div class="cred-content">
            <span>${escapeHtml(label)}</span>
            <code>${escapeHtml(String(value))}</code>
          </div>
          <button class="mini-button" type="button" onclick='copyText(${encodedValue}, this)'>Copy</button>
        </div>
      `;
    }

    function setRunningState(running) {
      document.getElementById('submitButton').disabled = running;
    }

    async function copyText(value, button) {
      try {
        await navigator.clipboard.writeText(String(value));
        if (button) {
          const previous = button.textContent;
          button.textContent = 'Copied';
          button.classList.add('copy-ok');
          setTimeout(() => {
            button.textContent = previous;
            button.classList.remove('copy-ok');
          }, 1200);
        }
      } catch (error) {
        console.error(error);
      }
    }

    function copyCredentialBundle(button, encodedCredentials) {
      const credentials = decodeCredentialArg(encodedCredentials);
      const rows = [
        ['Domain', credentials.domain],
        ['cPanel Username', credentials.cpanel_username],
        ['cPanel Password', credentials.cpanel_account_password || 'Existing account password not re-shown'],
        ['Support Email', credentials.support_email],
        ['Support Email Password', credentials.support_email_password],
        ['Database Name', credentials.database_name],
        ['Database User', credentials.database_user],
        ['Database Password', credentials.database_user_password],
        ['Nameservers', (credentials.nameservers || []).join(', ')],
      ].filter(([, value]) => value);
      copyText(rows.map(([label, value]) => `${label}: ${value}`).join('\\n'), button);
    }

    function downloadCredentialBundle(encodedCredentials, domain) {
      const credentials = decodeCredentialArg(encodedCredentials);
      const safeName = String(domain || 'credentials').replace(/[^a-z0-9._-]+/gi, '_');
      const blob = new Blob([JSON.stringify(credentials, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${safeName}-credentials.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    }

    function encodeCredentialArg(value) {
      return encodeURIComponent(JSON.stringify(value || {}));
    }

    function decodeCredentialArg(value) {
      return JSON.parse(decodeURIComponent(String(value || '')));
    }

    function escapeHtml(value) {
      return String(value || '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));
    }

    function titleize(value) {
      return String(value || '').replaceAll('-', ' ').replace(/\\b\\w/g, char => char.toUpperCase());
    }

    document.getElementById('runForm').addEventListener('submit', submitRun);
    document.getElementById('refreshButton').addEventListener('click', loadHistory);
    boot();
  </script>
</body>
</html>"""


class RunManager:
    def __init__(self, settings: Settings, config: AppConfig, state: StateStore) -> None:
        self.settings = settings
        self.config = config
        self.state = state
        self._lock = threading.Lock()
        self._runs: dict[str, dict[str, Any]] = {}

    def start_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        kind = str(payload.get("kind", "")).strip().lower()
        server = str(payload.get("server", "")).strip().lower()
        offer_path = str(payload.get("offer_path", "")).strip()
        domains = self._parse_domains(payload.get("domains", ""))
        if not kind or not server:
            raise ValueError("Stack and server are required.")
        if not offer_path:
            raise ValueError("Slug / offer path is required.")
        if not domains:
            raise ValueError("At least one domain is required.")

        profile = self.config.resolve_profile_for_kind_server(kind, server)
        run_id = uuid.uuid4().hex
        jobs = [DomainJob(domain=domain, profile=profile, offer_path=offer_path) for domain in domains]
        created_at = datetime.now(timezone.utc).isoformat()
        run_state = {
            "run_id": run_id,
            "profile": profile,
            "kind": kind,
            "server": server,
            "status": StepStatus.RUNNING.value,
            "status_message": f"Queued {len(jobs)} domain{'s' if len(jobs) != 1 else ''} for provisioning.",
            "created_at": created_at,
            "finished_at": "",
            "jobs": [
                {"domain": job.domain, "profile": job.profile, "status": StepStatus.PENDING.value, "steps": []}
                for job in jobs
            ],
            "dry_run": bool(payload.get("dry_run", False)),
            "orange_browser": bool(payload.get("orange_browser", True)),
        }
        with self._lock:
            self._runs[run_id] = run_state

        worker = threading.Thread(
            target=self._run_jobs,
            args=(run_id, jobs, bool(payload.get("dry_run", False)), bool(payload.get("orange_browser", True))),
            daemon=True,
        )
        worker.start()
        return {"run_id": run_id, "profile": profile}

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            run = self._runs.get(run_id)
            return json.loads(json.dumps(run)) if run is not None else None

    def _run_jobs(self, run_id: str, jobs: list[DomainJob], dry_run: bool, orange_browser: bool) -> None:
        run_failed = False
        for job in jobs:
            self._set_run_status(run_id, StepStatus.RUNNING.value, f"Working on {job.domain}.")
            provisioner = OfferProvisioner(
                self.settings,
                self.config,
                self.state,
                dry_run=dry_run,
                use_orange_browser=orange_browser,
                progress_callback=lambda result, domain=job.domain: self._update_job(run_id, domain, result),
            )
            result = provisioner.run(job)
            if result.status == StepStatus.FAILED:
                run_failed = True
        final_status = StepStatus.FAILED.value if run_failed else StepStatus.DONE.value
        self._set_run_status(run_id, final_status, "Provisioning finished.")
        with self._lock:
            if run_id in self._runs:
                self._runs[run_id]["finished_at"] = datetime.now(timezone.utc).isoformat()

    def _update_job(self, run_id: str, domain: str, result: dict[str, object]) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            jobs = run.get("jobs", [])
            for index, job in enumerate(jobs):
                if job.get("domain") == domain:
                    jobs[index] = result
                    break
            run["status_message"] = self._status_message_for_run(run)

    def _set_run_status(self, run_id: str, status: str, message: str) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            run["status"] = status
            run["status_message"] = message

    def _status_message_for_run(self, run: dict[str, Any]) -> str:
        for job in run.get("jobs", []):
            running_steps = [step for step in job.get("steps", []) if step.get("status") == StepStatus.RUNNING.value]
            if running_steps:
                current_step = running_steps[-1]
                return f"{job.get('domain')}: {current_step.get('message') or current_step.get('name')}"
        failed = [job for job in run.get("jobs", []) if job.get("status") == StepStatus.FAILED.value]
        if failed:
            return f"Finished with errors on {len(failed)} domain{'s' if len(failed) != 1 else ''}."
        done = [job for job in run.get("jobs", []) if job.get("status") == StepStatus.DONE.value]
        if done and len(done) == len(run.get("jobs", [])):
            return "All domains finished successfully."
        return run.get("status_message", "Preparing run.")

    @staticmethod
    def _parse_domains(raw: object) -> list[str]:
        parts = re.split(r"[\s,;]+", str(raw).strip())
        domains: list[str] = []
        seen: set[str] = set()
        for part in parts:
            domain = part.strip().lower()
            if not domain or "." not in domain or domain in seen:
                continue
            domains.append(domain)
            seen.add(domain)
        return domains


def serve(host: str, port: int, settings: Settings, config: AppConfig, state: StateStore) -> None:
    manager = RunManager(settings, config, state)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/" or parsed.path.startswith("/index.html"):
                self._send(200, INDEX, "text/html; charset=utf-8")
                return
            if parsed.path == "/api/state":
                self._send_json(200, state.read())
                return
            if parsed.path == "/api/config":
                profiles = config.profile_summaries()
                kinds = sorted({str(item["kind"]) for item in profiles if item["kind"]})
                server_choices = {kind: config.server_choices_for_kind(kind) for kind in kinds}
                profile_lookup = {
                    kind: {server: config.resolve_profile_for_kind_server(kind, server) for server in server_choices[kind]}
                    for kind in kinds
                }
                payload = {
                    "config_path": str(settings.config_path),
                    "state_path": str(settings.state_path),
                    "profiles": profiles,
                    "kinds": kinds,
                    "servers": sorted({server for item in profiles for server in item["servers"]}),
                    "server_choices": server_choices,
                    "profile_lookup": profile_lookup,
                }
                self._send_json(200, payload)
                return
            if parsed.path.startswith("/api/runs/"):
                run_id = parsed.path.rsplit("/", 1)[-1]
                payload = manager.get_run(run_id)
                if payload is None:
                    self._send_json(404, {"error": "run not found"})
                    return
                self._send_json(200, payload)
                return
            self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/run":
                self._send_json(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length) if length else b"{}")
                result = manager.start_run(payload)
            except Exception as exc:
                self._send_json(400, {"error": str(exc)})
                return
            self._send_json(202, result)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

        def _send(self, status: int, payload: str | bytes, content_type: str) -> None:
            body = payload.encode("utf-8") if isinstance(payload, str) else payload
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    print(f"OfferOps dashboard: http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()

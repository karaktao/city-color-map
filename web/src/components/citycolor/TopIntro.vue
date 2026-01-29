<template>
  <div class="top-intro">
    <div class="brand">
      <div class="logo-icon">🎨</div>
      <div class="titles">
        <h2>City Color Analysis Wizard</h2>
        <span class="subtitle">Urban Street View Analysis</span>
      </div>
    </div>
    <div class="workflow-hint">
      <div class="step-item">Init</div>
      <span class="arrow">→</span>
      <div class="step-item">BBOX</div>
      <span class="arrow">→</span>
      <div class="step-item">Fetch</div>
      <span class="arrow">→</span>
      <div class="step-item">Process</div>
      <span class="arrow">→</span>
      <div class="step-item">Map</div>
    </div>
  </div>
</template>

<style scoped>
.top-intro {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  height: 64px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  font-size: 24px;
  background: #ecfdf5;
  padding: 8px;
  border-radius: 8px;
}

.titles h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #111827;
}

.subtitle {
  font-size: 12px;
  color: #6b7280;
  letter-spacing: 0.5px;
}

.workflow-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #6b7280;
}

.step-item {
  background: #f3f4f6;
  padding: 4px 10px;
  border-radius: 4px;
  color: #374151;
  font-weight: 500;
}

.arrow {
  color: #d1d5db;
}
</style>
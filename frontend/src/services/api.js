import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.response.use(
  res => res,
  err => {
    const msg = err.response?.data?.detail || err.message || 'API Error';
    return Promise.reject(new Error(msg));
  }
)

export const insuranceAPI = {
  // Predictions
  predictPremium:  (data) => api.post('/predict/premium', data),
  predictRiskOnly: (data) => api.post('/predict/risk-only', data),

  // Vehicle catalogue — from DB
  getVehicleModels: () => api.get('/vehicles/models'),
  getVehicleTypes:  () => api.get('/vehicles/types'),

  // Policy
  registerPolicy: (data) => api.post('/policy/register', data),
  issuePolicy:    (data) => api.post('/policy/issue', data),
  getPolicy:      (id)   => api.get(`/policy/${id}`),
  listPolicies:   (skip=0, limit=20) => api.get(`/policies?skip=${skip}&limit=${limit}`),

  // Renewal
  getRenewalPolicy: (policyId) => api.get(`/renewal/policy/${policyId}`),
  calculateRenewal: (data) => api.post('/renewal/calculate', data),
  processRenewal:   (data) => api.post('/renewal/process', data),
  listRenewals:     ()     => api.get('/renewals'),

  // Claims
  submitClaim: (data) => api.post('/claim/submit', data),
  getClaim:    (id)   => api.get(`/claim/${id}`),
  listClaims:  (status) => api.get('/claims' + (status ? `?status=${status}` : '')),

  // Dashboard
  getDashboardStats:    () => api.get('/dashboard/stats'),
  getAgeRisk:           () => api.get('/dashboard/age-risk'),
  getProvinceRisk:      () => api.get('/dashboard/province-risk'),
  getClaimTypes:        () => api.get('/dashboard/claim-types'),
  getFeatureImportance: () => api.get('/dashboard/feature-importance'),
  getModelMetrics:      () => api.get('/dashboard/model-metrics'),
}

export default insuranceAPI

// Explainability
export const explainAPI = {
  explain: (proposal) => fetch('/api/v1/explain', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(proposal)
  }).then(r => r.json()),

  purePremium: (data) => fetch('/api/v1/actuarial/pure-premium', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(data)
  }).then(r => r.json()),

  modelCard: () => fetch('/api/v1/governance/model-card').then(r => r.json()),
  registry:  () => fetch('/api/v1/governance/registry').then(r => r.json()),
  threshold: () => fetch('/api/v1/governance/threshold').then(r => r.json()),
  psiStatus: () => fetch('/api/v1/governance/psi-check').then(r => r.json()),
}

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
  predictPremium:  (data) => api.post('/predict/premium', data),
  predictRiskOnly: (data) => api.post('/predict/risk-only', data),

  getVehicleModels: () => api.get('/vehicles/models'),
  getVehicleTypes:  () => api.get('/vehicles/types'),
  getPoliciesList:  (q = '', limit = 20) => api.get(`/policies/list?q=${encodeURIComponent(q)}&limit=${limit}`),

  registerPolicy: (data) => api.post('/policy/register', data),
  issuePolicy:    (data) => api.post('/policy/issue', data),
  getPolicy:      (id)   => api.get(`/policy/${id}`),
  listPolicies:   (skip=0, limit=20) => api.get(`/policies?skip=${skip}&limit=${limit}`),

  getRenewalPolicy: (policyId) => api.get(`/renewal/policy/${policyId}`),
  calculateRenewal: (data) => api.post('/renewal/calculate', data),
  processRenewal:   (data) => api.post('/renewal/process', data),
  listRenewals:     ()     => api.get('/renewals'),

  submitClaim: (data) => api.post('/claim/submit', data),
  getClaim:    (id)   => api.get(`/claim/${id}`),
  listClaims:  (status) => api.get('/claims' + (status ? `?status=${status}` : '')),

  getDashboardStats:    () => api.get('/dashboard/stats'),
  getAgeRisk:           () => api.get('/dashboard/age-risk'),
  getProvinceRisk:      () => api.get('/dashboard/province-risk'),
  getClaimTypes:        () => api.get('/dashboard/claim-types'),
  getFeatureImportance: () => api.get('/dashboard/feature-importance'),
  getModelMetrics:      () => api.get('/dashboard/model-metrics'),
}

export default insuranceAPI

export const explainAPI = {
  explain:     (proposal) => api.post('/explain', proposal),
  purePremium: (data)     => api.post('/actuarial/pure-premium', data),
  modelCard:   ()         => api.get('/governance/model-card'),
  registry:    ()         => api.get('/governance/registry'),
  threshold:   ()         => api.get('/governance/threshold'),
  psiStatus:   ()         => api.get('/governance/psi-check'),
}

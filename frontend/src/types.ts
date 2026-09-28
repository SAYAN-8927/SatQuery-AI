export interface BandPreview {
  band: string;
  name: string;
  wavelength: string;
  preview_url: string;
  color: string;
}

export interface CompositePreview {
  type: string;
  label: string;
  url: string;
}

export interface SceneInfo {
  scene_id: string;
  title?: string;
  satellite?: string;
  sensor?: string;
  acquisition_date?: string;
  date?: string;
  path_row?: string;
  path_row_formatted?: string;
  crs?: string;
  resolution?: string;
  file_count: number;
  bands: string[];
  modality: 'optical' | 'sar' | string;
  thumbnail?: string;
  thumbnail_url?: string;
  is_generic_image?: boolean;
  input_category?: string;
  image_format?: string;
  dimensions?: string;
  width?: number;
  height?: number;
  channels?: string;
  source_file?: string;
  geospatial_metadata?: string;
  band_previews?: BandPreview[];
  composite_previews?: CompositePreview[];
  available_analyses: {
    ndvi?: boolean;
    rgb?: boolean;
    multispectral?: boolean;
    sar_dual_pol?: boolean;
    sar_backscatter?: boolean;
    [key: string]: boolean | undefined;
  };
  can_delete?: boolean;
}

export interface BiTemporalPair {
  before: SceneInfo;
  after: SceneInfo;
  before_date?: string;
  after_date?: string;
  interval_days?: number;
  path_row?: string;
  path_row_formatted?: string;
  crs?: string;
  same_satellite?: boolean;
  detection_method?: string;
  spatial_compatibility?: {
    same_path_row: boolean;
    same_crs: boolean;
    bands_available: boolean;
  };
}

export interface MultimodalPair {
  pair_id: string;
  pair_type: 'optical_sar';
  location: string;
  optical_scene_id: string;
  sar_scene_id: string;
  optical_scene?: SceneInfo;
  sar_scene?: SceneInfo;
  optical_satellite?: string;
  sar_satellite?: string;
  optical_acquisition_date?: string;
  sar_acquisition_date?: string;
  temporal_gap_days: number;
  spatial_overlap: boolean;
  status: string;
  detection_method?: string;
  optical_preview?: string;
  sar_preview?: string;
  optical_bands?: string[];
  sar_polarizations?: string[];
  is_custom?: boolean;
}

export interface SceneData {
  success: boolean;
  file_count: number;
  scene_count: number;
  input_type: string;
  scenes: SceneInfo[];
  bi_temporal_pairs: BiTemporalPair[];
  multimodal_pairs?: MultimodalPair[];
}

export interface ExampleQuery {
  id: string;
  label: string;
  icon: string;
  query: string;
  description: string;
  explanation: string;
  badge: string;
}

export interface ExecutionStep {
  step: string;
  status: string;
  timestamp: string;
  details?: Record<string, any>;
}

export interface ExecutionTrace {
  user_query: string;
  execution_id: string;
  status: string;
  total_execution_time_seconds?: number;
  steps: ExecutionStep[];
}

export interface ConfidenceInfo {
  score: number;
  level: 'high' | 'medium' | 'low' | string;
  basis: string[];
}

export interface Evidence {
  ndvi_map?: string;
  change_map?: string;
  comparison_triplet?: string;
  spectral_profile_chart?: string;
  fusion_composite?: string;
  before_rgb?: string;
  after_rgb?: string;
  [key: string]: string | undefined;
}

export interface AnalysisComponent {
  intent: string;
  tool?: string;
  tool_name?: string;
  status: 'executed' | 'blocked' | 'failed' | 'unsupported' | string;
  title?: string;
  summary?: string;
  message?: string;
  error?: string;
  metrics?: Record<string, any>;
  evidence?: Evidence;
}

export interface QueryResult {
  success: boolean;
  query: string;
  multi_intent?: boolean;
  intent: string;
  primary_intent?: string;
  secondary_intents?: string[];
  intents?: any[];
  intent_reason?: string;
  selected_tool: string;
  selected_tools?: string[];
  tool_description?: string;
  components?: AnalysisComponent[];
  analysis?: {
    answer?: string;
    model?: string;
    evidence?: Evidence;
    statistics?: Record<string, any>;
    ndvi_statistics?: Record<string, any>;
    spectral_indices?: Record<string, any>;
    spectral_signature_classification?: string;
    optical_metrics?: Record<string, any>;
    sar_metrics?: Record<string, any>;
    fusion_metrics?: Record<string, any>;
    components?: AnalysisComponent[];
    vlm_synthesis?: {
      success: boolean;
      answer?: string;
    };
    [key: string]: any;
  };
  interpretation?: {
    success: boolean;
    interpretation: string;
    headline?: string;
    confidence?: ConfidenceInfo;
    dynamic_classification?: string;
    vegetation_category?: string;
    basis?: Record<string, any>;
  };
  execution_trace?: ExecutionTrace;
  error?: string;
  suggested_action?: string;
  source_scene_id?: string;
  source_scene_name?: string;
  source_dates?: string;
  source_sensor?: string;
  source_modality?: string;
  source_bands?: string[];
  before_scene_id?: string;
  after_scene_id?: string;
  before_date?: string;
  after_date?: string;
  analyzed_scene?: AnalyzedSceneMeta;
}

export interface AnalyzedSceneMeta {
  scene_id: string;
  title: string;
  source_scene_id?: string;
  source_scene_name?: string;
  source_sensor?: string;
  source_dates?: string;
  source_modality?: string;
  source_bands?: string[];
  satellite?: string;
  sensor?: string;
  date?: string;
  acquisition_date?: string;
  path_row_formatted?: string;
  resolution?: string;
  crs?: string;
  thumbnail?: string;
  bands?: string[];
  mode?: string;
  before?: any;
  after?: any;
  optical_scene?: any;
  sar_scene?: any;
  before_scene_id?: string;
  after_scene_id?: string;
  before_date?: string;
  after_date?: string;
}

export interface QueryPayload {
  query: string;
  active_scene_id?: string;
  active_scene_files?: string[];
  selected_scenario?: string;
  scene_id?: string;
  selected_scene_id?: string;
  mode?: 'single_scene' | 'bitemporal' | 'multimodal_pair' | 'fusion' | string;
  before_scene_id?: string;
  after_scene_id?: string;
  optical_scene_id?: string;
  sar_scene_id?: string;
  active_pair_type?: string;
  active_pair_id?: string;
  workspace_id?: string;
}

export interface DeleteSceneResponse {
  success: boolean;
  scene_id: string;
  workspace_id: string;
  deleted_files: string[];
  deleted_count: number;
}

export interface WorkspaceInfo {
  workspace_id: string;
  created_at: string;
  last_active_at: string;
  expiry_hours: number;
  file_count: number;
  files: string[];
}

export interface UploadResponse {
  success: boolean;
  filename: string;
  saved_path: string;
  scene_id?: string;
  classification?: {
    satellite?: string;
    modality?: string;
    category?: string;
    description?: string;
  };
  band_information?: {
    identified: boolean;
    band?: string;
    band_name?: string;
    wavelength_microns?: string;
    common_use?: string;
  };
  preview?: {
    preview_url?: string;
  };
  error?: string;
}

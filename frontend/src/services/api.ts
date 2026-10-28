import axios from 'axios';
import { supabase } from './supabase';
import { Video, VideoDetail, ChatMessage } from '../types';

const getBackendBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_BACKEND_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim() !== '') {
    const trimmed = envUrl.trim().replace(/\/+$/, '');
    if (import.meta.env.PROD && (trimmed.includes('localhost') || trimmed.includes('127.0.0.1'))) {
      console.warn(
        '[API Config Warning] VITE_BACKEND_URL is set to localhost in a production environment: ' +
          trimmed +
          '. In production on Vercel, set VITE_BACKEND_URL to your hosted backend URL (e.g. Render, Railway).'
      );
    }
    return trimmed;
  }
  // Never default to localhost in production mode to avoid mixed-content and connection failures
  if (import.meta.env.PROD) {
    console.warn(
      '[API Config Notice] VITE_BACKEND_URL is not set in production. ' +
        'Please add VITE_BACKEND_URL to your Vercel project environment variables.'
    );
    return '';
  }
  return 'http://localhost:8000';
};

const BACKEND_URL = getBackendBaseUrl();

export const apiClient = axios.create({
  baseURL: BACKEND_URL || undefined,
});

// Interceptor to attach Supabase JWT bearer token
apiClient.interceptors.request.use(async (config) => {
  try {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch (err) {
    console.warn('Could not retrieve Supabase session token:', err);
  }
  return config;
});

export interface PresignedUploadUrlResponse {
  video_id: string;
  upload_url: string | null;
  token: string | null;
  bucket: string | null;
  path: string | null;
  storage_path: string | null;
  direct_upload: boolean;
}

export interface CompleteUploadPayload {
  video_id: string;
  storage_path: string;
  title: string;
  original_filename: string;
  file_size_bytes: number;
}

export const api = {
  // Direct & Server Video Upload Management
  async createUploadUrl(
    filename: string,
    fileSize: number,
    contentType?: string,
    title?: string
  ): Promise<PresignedUploadUrlResponse> {
    const res = await apiClient.post<PresignedUploadUrlResponse>('/api/videos/create-upload-url', {
      filename,
      file_size: fileSize,
      content_type: contentType,
      title,
    });
    return res.data;
  },

  async completeUpload(payload: CompleteUploadPayload): Promise<Video> {
    const res = await apiClient.post<Video>('/api/videos/complete-upload', payload);
    return res.data;
  },

  async uploadDirectToStorage(
    uploadUrl: string,
    bucket: string | null,
    objectPath: string | null,
    token: string | null,
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<void> {
    // 1. Direct PUT with raw file (standard for S3/Supabase signed URLs)
    try {
      await axios.put(uploadUrl, file, {
        headers: {
          'Content-Type': file.type || 'video/mp4',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && onProgress) {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            onProgress(percent);
          }
        },
      });
      return;
    } catch (putErr) {
      console.warn('[Direct Upload] PUT attempt failed, trying multipart POST:', putErr);
    }

    // 2. Fallback: multipart FormData POST (Supabase Storage upload-to-sign format)
    try {
      const formData = new FormData();
      formData.append('cacheControl', '3600');
      formData.append('', file, file.name);

      await axios.post(uploadUrl, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total && onProgress) {
            const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            onProgress(percent);
          }
        },
      });
      return;
    } catch (postErr) {
      console.warn('[Direct Upload] FormData POST failed, trying supabase-js SDK fallback:', postErr);
    }

    // 3. Fallback: supabase-js SDK uploadToSignedUrl if bucket/token are present
    if (bucket && objectPath && token) {
      const { error } = await supabase.storage.from(bucket).uploadToSignedUrl(objectPath, token, file);
      if (error) throw error;
      if (onProgress) onProgress(100);
      return;
    }

    throw new Error('All direct object storage upload methods failed.');
  },

  async uploadVideo(
    file: File,
    title?: string,
    onProgress?: (percent: number) => void
  ): Promise<Video> {
    const projectTitle = title?.trim() || file.name.replace(/\.[^/.]+$/, '');

    // Attempt direct-to-storage upload first to bypass serverless payload limits (Vercel 4.5MB limit)
    try {
      const presigned = await this.createUploadUrl(
        file.name,
        file.size,
        file.type || 'video/mp4',
        projectTitle
      );

      if (presigned.direct_upload && presigned.upload_url && presigned.storage_path) {
        await this.uploadDirectToStorage(
          presigned.upload_url,
          presigned.bucket,
          presigned.path,
          presigned.token,
          file,
          onProgress
        );

        const video = await this.completeUpload({
          video_id: presigned.video_id,
          storage_path: presigned.storage_path,
          title: projectTitle,
          original_filename: file.name,
          file_size_bytes: file.size,
        });

        return video;
      }
    } catch (directErr: any) {
      console.warn(
        '[Direct Upload Notice] Direct storage upload bypassed or failed, falling back to server upload:',
        directErr.message || directErr
      );
      // On Vercel production without a custom backend, files > 4.5MB cannot fall back to /api/videos/upload
      if (file.size > 4.5 * 1024 * 1024 && !BACKEND_URL && import.meta.env.PROD) {
        throw new Error(
          `Direct object storage upload failed: ${directErr.message || 'Network error'}. ` +
          `Vercel serverless functions strictly reject payloads exceeding 4.5MB. ` +
          `Please check your Supabase Storage bucket ('media-vault') CORS and credentials, or upload a smaller clip.`
        );
      }
    }

    // Standard fallback: multipart/form-data upload to backend (local dev or small files)
    const formData = new FormData();
    formData.append('file', file);
    if (title) formData.append('title', title);

    const res = await apiClient.post<Video>('/api/videos/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });
    return res.data;
  },

  async importVideoUrl(url: string, title?: string): Promise<Video> {
    const res = await apiClient.post<Video>('/api/videos/import-url', { url, title });
    return res.data;
  },

  async listVideos(): Promise<Video[]> {
    const res = await apiClient.get<Video[]>('/api/videos');
    return res.data;
  },

  async getVideoDetail(videoId: string): Promise<VideoDetail> {
    const res = await apiClient.get<VideoDetail>(`/api/videos/${videoId}`);
    return res.data;
  },

  async getVideoStatus(videoId: string): Promise<{ status: string; progress_percent: number; error_message?: string }> {
    const res = await apiClient.get(`/api/videos/${videoId}/status`);
    return res.data;
  },

  async deleteVideo(videoId: string): Promise<void> {
    await apiClient.delete(`/api/videos/${videoId}`);
  },

  // Transcript & Diarization
  async renameSpeaker(videoId: string, speakerLabel: string, newDisplayName: string): Promise<void> {
    await apiClient.patch(`/api/videos/${videoId}/speakers`, {
      speaker_label: speakerLabel,
      new_display_name: newDisplayName,
    });
  },

  async searchTranscript(videoId: string, query: string) {
    const res = await apiClient.get(`/api/videos/${videoId}/transcript/search`, {
      params: { q: query },
    });
    return res.data;
  },

  // Q&A / Chat
  async askQuestion(videoId: string, question: string) {
    const res = await apiClient.post(`/api/videos/${videoId}/chat`, {
      video_id: videoId,
      question,
    });
    return res.data;
  },

  // Multilingual Translation
  async translateContent(videoId: string, targetLanguage: string) {
    const res = await apiClient.post(`/api/videos/${videoId}/translate`, {
      target_language: targetLanguage,
    });
    return res.data;
  },

  async translateSubtitles(videoId: string, targetLanguage: string) {
    const res = await apiClient.post(`/api/videos/${videoId}/subtitles/translate`, {
      target_language: targetLanguage,
    });
    return res.data;
  },

  // Export & Download
  getExportUrl(videoId: string, format: 'pdf' | 'docx' | 'txt' | 'srt' | 'vtt', token?: string): string {
    const query = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${BACKEND_URL}/api/videos/${videoId}/export/${format}${query}`;
  },

  async downloadExport(
    videoId: string,
    format: 'pdf' | 'docx' | 'txt' | 'srt' | 'vtt',
    filename?: string,
    params?: Record<string, string>
  ): Promise<void> {
    const res = await apiClient.get(`/api/videos/${videoId}/export/${format}`, {
      params,
      responseType: 'blob',
    });
    const contentType = typeof res.headers['content-type'] === 'string'
      ? res.headers['content-type']
      : 'application/octet-stream';
    const blob = new Blob([res.data], { type: contentType });

    let downloadName = filename;
    const cd = res.headers['content-disposition'];
    if (typeof cd === 'string') {
      const utfMatch = cd.match(/filename\*=UTF-8''([^;]+)/i);
      if (utfMatch && utfMatch[1]) {
        try {
          downloadName = decodeURIComponent(utfMatch[1]);
        } catch (_) {}
      } else {
        const match = cd.match(/filename="?([^";]+)"?/i);
        if (match && match[1]) {
          downloadName = match[1];
        }
      }
    }

    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = downloadName || `video_${videoId}_export.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
  },

  getVideoStreamUrl(videoId: string, token?: string): string {
    const query = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${BACKEND_URL}/api/videos/${videoId}/stream${query}`;
  },

  // Auth Helpers
  async registerUser(
    email: string,
    password: string,
    fullName?: string
  ): Promise<{ success: boolean; message: string; user_id?: string }> {
    const res = await apiClient.post('/api/auth/register', {
      email,
      password,
      full_name: fullName,
    });
    return res.data;
  },

  async checkAuthMethod(
    email: string
  ): Promise<{ exists: boolean; has_google: boolean; has_email: boolean; is_confirmed: boolean }> {
    const res = await apiClient.post('/api/auth/check-method', { email });
    return res.data;
  },

  async confirmAccount(
    email: string
  ): Promise<{ success: boolean; message: string }> {
    const res = await apiClient.post('/api/auth/confirm-account', { email });
    return res.data;
  },
};



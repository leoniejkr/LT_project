import type { paths } from "./api-types";

// Hilfstyp für API-Antworten
export type ApiResponse<T extends keyof paths, M extends keyof paths[T]> = 
    paths[T][M] extends { responses: { 202: { schema: infer S } } } ? S : any;

// Hilfstyp für API-Payloads (POST)
export type ApiRequest<T extends keyof paths> = 
    paths[T]["post"] extends { parameters: { formData: infer P } } ? P : any;

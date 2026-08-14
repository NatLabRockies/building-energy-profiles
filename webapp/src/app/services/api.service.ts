import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  AvailableCountiesResponse,
  AvailableStatesResponse,
  BuildingDistributionRequest,
  BuildingDistributionResponse,
  CompositeResolveRequest,
  CompositeResolveResponse,
  EnergyStarTypeInfo,
  FilterOptionsRequest,
  FilterOptionsResponse,
  MeasuresCompareRequest,
  MeasuresCompareResponse,
  MeasuresListResponse,
  MetadataSummaryRequest,
  MetadataSummaryResponse,
  MosExportRequest,
  Product,
  TimeseriesRequest,
  TimeseriesResponse,
} from '../models/api.models';

/** Thin HttpClient wrapper for the composite building explorer API (see api/main.py). */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly baseUrl = environment.apiBaseUrl;

  constructor(private readonly http: HttpClient) {}

  getEnergyStarTypes(): Observable<EnergyStarTypeInfo[]> {
    return this.http.get<EnergyStarTypeInfo[]>(`${this.baseUrl}/energy-star-types`);
  }

  resolveComposite(request: CompositeResolveRequest): Observable<CompositeResolveResponse> {
    return this.http.post<CompositeResolveResponse>(`${this.baseUrl}/composite/resolve`, request);
  }

  getBuildingDistributions(request: BuildingDistributionRequest): Observable<BuildingDistributionResponse> {
    return this.http.post<BuildingDistributionResponse>(`${this.baseUrl}/composite/building-distribution`, request);
  }

  getFilterOptions(request: FilterOptionsRequest): Observable<FilterOptionsResponse> {
    return this.http.post<FilterOptionsResponse>(`${this.baseUrl}/composite/filter-options`, request);
  }

  getMetadataSummary(request: MetadataSummaryRequest): Observable<MetadataSummaryResponse> {
    return this.http.post<MetadataSummaryResponse>(`${this.baseUrl}/metadata/summary`, request);
  }

  getCompositeTimeseries(request: TimeseriesRequest): Observable<TimeseriesResponse> {
    return this.http.post<TimeseriesResponse>(`${this.baseUrl}/timeseries/composite`, request);
  }

  getMeasures(product: Product, release?: string): Observable<MeasuresListResponse> {
    let params = new HttpParams().set('product', product);
    if (release) {
      params = params.set('release', release);
    }
    return this.http.get<MeasuresListResponse>(`${this.baseUrl}/measures`, { params });
  }

  getAvailableStates(product: Product, release?: string): Observable<AvailableStatesResponse> {
    let params = new HttpParams().set('product', product);
    if (release) {
      params = params.set('release', release);
    }
    return this.http.get<AvailableStatesResponse>(`${this.baseUrl}/locations/states`, { params });
  }

  getAvailableCounties(product: Product, state: string, release?: string): Observable<AvailableCountiesResponse> {
    let params = new HttpParams().set('product', product).set('state', state);
    if (release) {
      params = params.set('release', release);
    }
    return this.http.get<AvailableCountiesResponse>(`${this.baseUrl}/locations/counties`, { params });
  }

  compareMeasures(request: MeasuresCompareRequest): Observable<MeasuresCompareResponse> {
    return this.http.post<MeasuresCompareResponse>(`${this.baseUrl}/measures/compare`, request);
  }

  exportMos(request: MosExportRequest): Observable<Blob> {
    return this.http.post(`${this.baseUrl}/export/mos`, request, { responseType: 'blob' });
  }

  /** URL for one building's energy model file -- a gzipped OpenStudio ".osm.gz" model for ComStock, or a
   * ".zip" archive (bundling the OSM with its supporting files) for ResStock. `GET`-ing this URL 307s
   * straight to the public OEDI download, so it's meant to be used as a plain link `href` (opened in a new
   * tab) rather than fetched via HttpClient. */
  getModelDownloadUrl(product: Product, bldgId: number, upgrade: string): string {
    const params = new HttpParams().set('product', product).set('bldg_id', bldgId).set('upgrade', upgrade);
    return `${this.baseUrl}/composite/model-download?${params.toString()}`;
  }
}

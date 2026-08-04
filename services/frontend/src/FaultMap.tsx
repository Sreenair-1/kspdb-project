import { useEffect, useRef } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import type { LatLngBoundsExpression } from "leaflet";

interface Ticket {
  id: string;
  incident_type: string;
  dt_id: string | null;
  feeder_id: string | null;
  upstream_pole_id: string | null;
  downstream_pole_id: string | null;
  latitude: number | null;
  longitude: number | null;
  confidence: number;
  affected_poles: number;
  lifecycle_status: string;
}

const BENGALURU: [number, number] = [12.9716, 77.5946];

function markerColor(type: string): string {
  if (type === "feeder") return "#f85149";
  if (type === "dt") return "#f0ab00";
  return "#d29922";
}

function BoundsAdjuster({ tickets }: { tickets: Ticket[] }) {
  const map = useMap();
  const prevCount = useRef(0);

  useEffect(() => {
    const mapped = tickets.filter((t) => t.latitude != null && t.longitude != null);
    if (mapped.length === 0) return;
    if (mapped.length === prevCount.current) return;
    prevCount.current = mapped.length;

    const bounds: LatLngBoundsExpression = mapped.map(
      (t) => [t.latitude!, t.longitude!] as [number, number],
    );
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
  }, [tickets, map]);

  return null;
}

interface Props {
  tickets: Ticket[];
}

export function FaultMap({ tickets }: Props) {
  const mapped = tickets.filter((t) => t.latitude != null && t.longitude != null);

  return (
    <div className="map-wrap">
      <MapContainer
        center={BENGALURU}
        zoom={13}
        style={{ height: "100%", width: "100%" }}
        scrollWheelZoom={true}
        zoomControl={true}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />
        <BoundsAdjuster tickets={tickets} />
        {mapped.map((t) => (
          <CircleMarker
            key={t.id}
            center={[t.latitude!, t.longitude!]}
            radius={9}
            pathOptions={{
              color: markerColor(t.incident_type),
              fillColor: markerColor(t.incident_type),
              fillOpacity: 0.85,
              weight: 2,
            }}
          >
            <Popup>
              <div style={{ minWidth: 160, fontSize: 12, lineHeight: 1.5 }}>
                <strong style={{ textTransform: "uppercase" }}>{t.incident_type}</strong>
                <br />
                <span style={{ color: "#555" }}>
                  {t.dt_id ?? t.feeder_id ?? "unknown"}
                </span>
                {t.upstream_pole_id && t.downstream_pole_id && (
                  <>
                    <br />
                    <span style={{ color: "#555", fontSize: 11 }}>
                      {t.upstream_pole_id} → {t.downstream_pole_id}
                    </span>
                  </>
                )}
                <br />
                <span>{t.affected_poles} poles affected</span>
                <br />
                <span>{Math.round(t.confidence * 100)}% confidence</span>
                <br />
                <span style={{ textTransform: "capitalize" }}>
                  {t.lifecycle_status.replace(/_/g, " ")}
                </span>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
      {mapped.length === 0 && (
        <div className="map-empty">
          No geolocated faults
        </div>
      )}
    </div>
  );
}

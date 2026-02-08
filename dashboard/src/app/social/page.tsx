"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SocialAccounts } from "@/components/social-accounts";

interface Post {
  postId: string;
  platform: string;
  content: string;
  publishedAt: string;
  likes: number;
  comments: number;
  shares: number;
  reach: number;
}

interface Insights {
  platform: string;
  followerCount: number;
  followerDelta: number;
  postsCount: number;
  totalReach: number;
  totalEngagement: number;
  engagementRate: number;
}

export default function SocialPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [insights, setInsights] = useState<Insights[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  async function fetchData() {
    setLoading(true);
    try {
      const [postsRes, fbInsights, twInsights] = await Promise.all([
        fetch("/api/social?action=posts"),
        fetch("/api/social?action=insights&platform=facebook"),
        fetch("/api/social?action=insights&platform=twitter"),
      ]);

      if (postsRes.ok) {
        const postsData = await postsRes.json();
        setPosts(Array.isArray(postsData) ? postsData : []);
      }

      const insightsData: Insights[] = [];
      if (fbInsights.ok) {
        const fb = await fbInsights.json();
        if (fb.platform) insightsData.push(fb);
      }
      if (twInsights.ok) {
        const tw = await twInsights.json();
        if (tw.platform) insightsData.push(tw);
      }
      setInsights(insightsData);
    } catch {
      // Social MCP not available
    } finally {
      setLoading(false);
    }
  }

  const platformIcons: Record<string, string> = {
    facebook: "📘",
    instagram: "📷",
    twitter: "🐦",
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Social Media</h1>
        <p className="text-muted-foreground">
          Manage your social media accounts and track engagement
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SocialAccounts />

        <Card>
          <CardHeader>
            <CardTitle>Analytics Overview</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading...</p>
            ) : insights.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Connect social accounts to view analytics
              </p>
            ) : (
              <div className="space-y-4">
                {insights.map((insight) => (
                  <div
                    key={insight.platform}
                    className="p-3 border rounded-lg"
                  >
                    <div className="flex items-center gap-2 mb-2">
                      <span>{platformIcons[insight.platform] || "📱"}</span>
                      <span className="font-medium capitalize">
                        {insight.platform}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-sm">
                      <div>
                        <p className="text-muted-foreground">Followers</p>
                        <p className="font-medium">
                          {insight.followerCount.toLocaleString()}
                          <span
                            className={`ml-1 text-xs ${
                              insight.followerDelta >= 0
                                ? "text-green-600"
                                : "text-red-600"
                            }`}
                          >
                            {insight.followerDelta >= 0 ? "+" : ""}
                            {insight.followerDelta}
                          </span>
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Reach</p>
                        <p className="font-medium">
                          {insight.totalReach.toLocaleString()}
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Engagement</p>
                        <p className="font-medium">{insight.engagementRate}%</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Posts</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : posts.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No posts yet. Connect accounts to get started.
            </p>
          ) : (
            <div className="space-y-4">
              {posts.map((post) => (
                <div
                  key={post.postId}
                  className="p-4 border rounded-lg"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span>{platformIcons[post.platform] || "📱"}</span>
                    <Badge variant="outline" className="capitalize">
                      {post.platform}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {new Date(post.publishedAt).toLocaleDateString()}
                    </span>
                  </div>
                  <p className="text-sm mb-3">{post.content}</p>
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>❤️ {post.likes}</span>
                    <span>💬 {post.comments}</span>
                    <span>🔄 {post.shares}</span>
                    <span>👁️ {post.reach.toLocaleString()} reach</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

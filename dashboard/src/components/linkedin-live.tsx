"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface LinkedInProfile {
  sub: string;
  name: string;
  email: string;
  picture: string;
}

interface LinkedInPost {
  id: string;
  text: string;
  createdAt: string;
  status: "published" | "failed";
}

interface StatusResponse {
  authenticated: boolean;
  profile: LinkedInProfile | null;
}

export function LinkedInLive() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [posts, setPosts] = useState<LinkedInPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [postsLoading, setPostsLoading] = useState(false);
  const [checked, setChecked] = useState(false);
  const [postsError, setPostsError] = useState<string | null>(null);
  const [postText, setPostText] = useState("");
  const [posting, setPosting] = useState(false);
  const [postResult, setPostResult] = useState<string | null>(null);

  const checkStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/linkedin/status");
      const data: StatusResponse = await res.json();
      setStatus(data);
      return data.authenticated;
    } catch {
      setStatus({ authenticated: false, profile: null });
      return false;
    } finally {
      setChecked(true);
      setLoading(false);
    }
  }, []);

  const fetchPosts = useCallback(async () => {
    setPostsLoading(true);
    setPostsError(null);
    try {
      const res = await fetch("/api/linkedin/posts");
      if (!res.ok) {
        const data = await res.json();
        setPostsError(data.error ?? "Failed to fetch posts");
        return;
      }
      const data = await res.json();
      setPosts(data.posts ?? []);
    } catch {
      setPostsError("Network error fetching posts");
    } finally {
      setPostsLoading(false);
    }
  }, []);

  const handlePost = async () => {
    if (!postText.trim()) return;
    setPosting(true);
    setPostResult(null);
    try {
      const res = await fetch("/api/linkedin/posts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: postText }),
      });
      const data = await res.json();
      if (res.ok) {
        setPostResult("Post published to LinkedIn!");
        setPostText("");
        fetchPosts();
      } else {
        setPostResult(`Error: ${data.error}`);
      }
    } catch {
      setPostResult("Network error creating post");
    } finally {
      setPosting(false);
    }
  };

  useEffect(() => {
    checkStatus().then((authed) => {
      if (authed) fetchPosts();
    });
  }, [checkStatus, fetchPosts]);

  const isConnected = status?.authenticated === true;
  const profile = status?.profile;

  return (
    <div className="space-y-4">
      {/* Connection status */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <CardTitle>LinkedIn</CardTitle>
              {isConnected ? (
                <Badge variant="default">
                  Connected: {profile?.name ?? profile?.email ?? "LinkedIn User"}
                </Badge>
              ) : checked ? (
                <Badge variant="destructive">Not Connected</Badge>
              ) : (
                <Badge variant="secondary">Checking...</Badge>
              )}
            </div>
            <div className="flex gap-2">
              {!isConnected && checked && (
                <Button asChild size="lg">
                  <a href="/api/linkedin/auth">Connect LinkedIn</a>
                </Button>
              )}
              {isConnected && (
                <Button variant="outline" onClick={fetchPosts} disabled={postsLoading}>
                  {postsLoading ? "Refreshing..." : "Refresh"}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {!isConnected && checked && (
            <p className="text-sm text-muted-foreground">
              Click <strong>Connect LinkedIn</strong> to authenticate and enable
              LinkedIn posting and monitoring.
            </p>
          )}

          {isConnected && profile && (
            <div className="flex items-center gap-4">
              {profile.picture && (
                <img
                  src={profile.picture}
                  alt={profile.name}
                  className="h-12 w-12 rounded-full"
                />
              )}
              <div>
                <p className="font-medium">{profile.name}</p>
                <p className="text-sm text-muted-foreground">{profile.email}</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Compose post */}
      {isConnected && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Create Post</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <textarea
              className="w-full rounded-md border bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring min-h-[120px] resize-y"
              placeholder="What do you want to talk about?"
              value={postText}
              onChange={(e) => setPostText(e.target.value)}
              maxLength={3000}
            />
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                {postText.length}/3000
              </span>
              <Button
                onClick={handlePost}
                disabled={posting || !postText.trim()}
              >
                {posting ? "Posting..." : "Post to LinkedIn"}
              </Button>
            </div>
            {postResult && (
              <p
                className={`text-sm ${
                  postResult.startsWith("Error")
                    ? "text-destructive"
                    : "text-green-600"
                }`}
              >
                {postResult}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Posts history */}
      {isConnected && (
        <>
          <h3 className="text-lg font-semibold">
            Post History ({posts.length})
          </h3>

          {postsError && (
            <Card>
              <CardContent className="py-4 text-sm text-destructive">
                {postsError}
              </CardContent>
            </Card>
          )}

          {postsLoading && posts.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                Loading posts...
              </CardContent>
            </Card>
          )}

          {!postsLoading && posts.length === 0 && !postsError && (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                No posts yet. Use the form above to create your first LinkedIn
                post.
              </CardContent>
            </Card>
          )}

          {posts.length > 0 && (
            <div className="grid gap-4 md:grid-cols-2">
              {posts.map((post) => (
                <Card key={post.id}>
                  <CardContent className="space-y-2 pt-6">
                    <p className="text-sm whitespace-pre-wrap">
                      {post.text || "(No text)"}
                    </p>
                    <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
                      <span>
                        {post.createdAt
                          ? new Date(post.createdAt).toLocaleString()
                          : ""}
                      </span>
                      <Badge
                        variant={
                          post.status === "published" ? "default" : "destructive"
                        }
                      >
                        {post.status === "published" ? "Published" : "Failed"}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
